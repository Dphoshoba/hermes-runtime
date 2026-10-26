# EVOSIA Production Deployment Guide

This document describes how to deploy EVOSIA to production, including
database configuration, environment variables, health checks, and
migration procedures.

## Database Configuration

### Authoritative Environment Variable

The primary database URL is configured via `EVOSIA_DATABASE_URL`.

Resolution order (runtime):
1. `EVOSIA_DATABASE_URL` (primary)
2. `HERMES_DATABASE_URL` (legacy fallback)
3. `sqlite:///./evosia_enterprise.db` (default local development)

Resolution order (Alembic migrations):
Same as runtime — `EVOSIA_DATABASE_URL` → `HERMES_DATABASE_URL` → default

### Local Development (SQLite)

No configuration required. The application defaults to a local SQLite file.

```bash
# Optional: set explicitly
export EVOSIA_DATABASE_URL="sqlite:///./evosia_enterprise.db"
```

### Docker Compose (M8 Testing)

The `docker-compose.yml` configures SQLite with a persistent volume:

```yaml
environment:
  EVOSIA_DATABASE_URL: "sqlite:///./data/evosia_m8.db"
volumes:
  - m8_data:/app/data
```

### Railway Deployment

Railway provides a `DATABASE_URL` environment variable by default.
The operator must map it to `EVOSIA_DATABASE_URL` in the Railway dashboard:

```
EVOSIA_DATABASE_URL=${DATABASE_URL}
```

**Note:** The actual database engine (PostgreSQL vs SQLite) depends on
Railway configuration. This is operator-controlled and not verifiable
from the repository alone.

## Migration Policy

### Current State

The container entrypoint verifies the configured SQLite backup, then runs
`python -m alembic -c enterprise/alembic.ini upgrade head`, and only starts
Uvicorn if both steps succeed. Railway attaches the service volume before
starting the container, so the migration targets the mounted database rather
than an ephemeral pre-deploy filesystem. The application then uses
`Base.metadata.create_all()` for tables outside the migration chain and
validates that the Computer Review schema is present.

### Migration Chain

| Migration | Tables Created |
|-----------|---------------|
| 001_initial | users, repositories, journal_events, findings, missions, reports |
| 002_scan_jobs | scan_jobs, scan_history + repository columns |
| 003_scan_hardening | scan_jobs hardening columns |
| 004_evidence_risk_gate | finding_adjudications + findings gate columns |
| 005_local_agent_devices | devices, bootstrap_tokens |
| 006_local_agent_projects | device_projects, project_authorization_tokens |
| 007_local_agent_scan_jobs | agent_jobs |
| 008_agent_job_truncation | agent_jobs.truncated |
| 009_computer_review_evidence | review identity, lifecycle, coverage, linked evidence, and database-enforced idempotency |
| 010_repository_ownership | repository tenant ownership |

The ORM also defines tables outside this migration chain; those continue to
be created by `create_all()` at startup.

### Fresh Database Procedure

The container startup entrypoint applies `alembic upgrade head` to the
configured database before launching Uvicorn. For production, set
`EVOSIA_SQLITE_BACKUP_PATH` to a separate SQLite backup file on the mounted
volume. Startup requires a file-backed SQLite database URL and a separate
mounted backup file, then runs SQLite integrity verification on the backup
before attempting a migration. A missing, invalid, or corrupt backup prevents
migration and application startup. Migration errors likewise prevent Uvicorn
from starting.
The integrity check confirms that SQLite can read the backup; it does not
establish that the backup is recent, complete, or recoverable as a pre-migration
snapshot. The operator must create and independently verify a current backup
before deploying a migration.

Alembic `upgrade head` is safe to repeat for a database already at head. The
entrypoint never stamps an unversioned database; an existing database created
by `create_all()` without a verified Alembic revision will fail closed rather
than be stamped or migrated over automatically.

### Existing Database Adoption (Production)

For databases created by `create_all()` before Alembic was integrated, do not
blindly stamp the current head. First inspect the schema and recorded Alembic
revision. Stamping does not apply missing schema changes.

For a database already at `008_agent_job_truncation`, the container startup
entrypoint applies the Computer Review and ownership migrations with
`alembic upgrade head`. For an older or unversioned database created by
`create_all()`, verify the existing schema and every migration effect
separately. Startup intentionally does not stamp or guess a revision.

Migration 009 refuses to create its active-review unique index if a project
already has multiple queued/running reviews. Resolve those rows deliberately
before retrying the migration; the migration will not cancel or discard work.
Migration 010 leaves existing repository rows unowned because the previous
schema contains no reliable owner attribution. Such rows remain hidden from
tenant-facing repository, Scans, Findings, Reports, and human-review endpoints
until a separately authorized attribution process assigns an owner.

```bash
# Only after verifying the database already has the complete current schema
alembic -c enterprise/alembic.ini stamp head
```

### Railway Release Sequence

Do not run SQLite operations from Railway's `preDeployCommand`: Railway does
not mount service volumes during pre-deploy commands. `railway.toml` therefore
has no pre-deploy migration command. After Railway attaches the service volume
and starts the new container, the Docker entrypoint verifies the mounted
backup, runs `python -m alembic -c enterprise/alembic.ini upgrade head`, and
executes `uvicorn enterprise.app:app --host 0.0.0.0 --port "${PORT:-8000}"`.
The entrypoint uses process replacement for Uvicorn, preserves the existing
host and port behavior, and stops before application startup on backup or
migration failure.

Set `EVOSIA_DATABASE_URL` to the mounted SQLite database URL and
`EVOSIA_SQLITE_BACKUP_PATH` to a separate, verified backup file on the volume.
The legacy `railway.toml` Config-as-Code format is deprecated; migrating this
configuration to Railway Infrastructure-as-Code is a separate follow-up and
is intentionally not part of this startup correction.

Before enabling this release sequence for an existing database, verify the
backup, Alembic revision, and schema, and resolve any duplicate active reviews.
Do not stamp or upgrade an unverified legacy schema automatically.

## Health and Readiness Endpoints

### `/api/health` — Liveness Probe

Returns lightweight liveness status. Always returns 200 when the process
is running. Does NOT check database connectivity.

```json
{"status": "ok", "version": "1.3.0"}
```

**Use for:** Docker HEALTHCHECK, load balancer liveness, Railway health.

### `/api/ready` — Readiness Probe

Verifies database connectivity. Returns 200 when database is reachable,
200 with degraded status when unreachable.

```json
{"status": "ok", "database": "connected"}
```

```json
{"status": "degraded", "database": "unavailable"}
```

**Use for:** Load balancer readiness, deployment verification.

**Never exposes:** Database URLs, credentials, or connection details.

### `/api/version` — Build Provenance

Returns version and build SHA for forensic identification.

```json
{"version": "1.3.0", "build_sha": "cc60c08", "provenance": "LIVE_EVOSIA_EVIDENCE"}
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `EVOSIA_JWT_SECRET` | JWT signing secret. Must be set to a real secret in production. |
| `EVOSIA_DATABASE_URL` | Database connection URL. |
| `EVOSIA_CORS_ALLOW_ORIGINS` | Comma-separated allowed origins for CORS. |

### Optional

| Variable | Description |
|----------|-------------|
| `EVOSIA_ENV` | `production` (default) or `development`. Development mode allows weak JWT secrets. |
| `EVOSIA_GEMINI_API_KEY` | Gemini API key. Graceful degradation if absent. |
| `EVOSIA_STATIC_DIR` | Override frontend asset location. |
| `EVOSIA_PREP_ROOT` | Preparation workspace root directory. |
| `EVOSIA_M8_FIXTURE` | `enabled` to allow fixture CLI operations. |

### Build-Time

| Variable | Description |
|----------|-------------|
| `EVOSIA_BUILD_SHA` | Git SHA baked into Docker image at build time. |
| `RAILWAY_GIT_COMMIT_SHA` | Injected by Railway at runtime. |

### Provider-Specific

| Variable | Description |
|----------|-------------|
| `PORT` | HTTP port (default: 8000). Set by Railway. |
| `DATABASE_URL` | Railway default database URL. Must be mapped to `EVOSIA_DATABASE_URL`. |

## Railway Configuration

### Deployment Model

- Railway deploys from Dockerfile (no `railway.json` required)
- Environment variables configured in Railway dashboard
- No repository configuration file needed

### Persistent Storage

Railway provides persistent storage for SQLite databases.
The `docker-compose.yml` uses named volumes for data persistence.

### Build Provenance

The Dockerfile bakes the git SHA into the image:
```dockerfile
ARG GIT_SHA=unknown
ENV EVOSIA_BUILD_SHA=${GIT_SHA}
```

Railway also injects `RAILWAY_GIT_COMMIT_SHA` at runtime.

## Production Verification

After deployment, verify:

```bash
# Health check
curl https://your-app.up.railway.app/api/health
# Expected: {"status":"ok","version":"1.3.0"}

# Readiness check
curl https://your-app.up.railway.app/api/ready
# Expected: {"status":"ok","database":"connected"}

# Version/provenance
curl https://your-app.up.railway.app/api/version
# Expected: {"version":"1.3.0","build_sha":"<commit>","provenance":"LIVE_EVOSIA_EVIDENCE"}
```

## Rollback/Recovery Limitations

- No automatic rollback mechanism
- Database migrations are forward-only (no downgrade migrations)
- To recover: redeploy previous Docker image version
- Data backup is operator responsibility

## Security Notes

- JWT secret must be set to a real secret in production
- CORS origins must be explicitly configured
- No secrets are exposed via health/version endpoints
- Authentication enforced on all API routes
- No execution authority is granted (execute/merge/deploy endpoints do not exist)
