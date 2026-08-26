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

The application uses `Base.metadata.create_all()` at startup to ensure
tables exist. Alembic migrations (001-004) exist but are not automatically
run at startup.

### Migration Chain

| Migration | Tables Created |
|-----------|---------------|
| 001_initial | users, repositories, journal_events, findings, missions, reports |
| 002_scan_jobs | scan_jobs, scan_history + repository columns |
| 003_scan_hardening | scan_jobs hardening columns |
| 004_evidence_risk_gate | finding_adjudications + findings gate columns |

**Important:** The ORM defines 19 tables, but migrations 001-004 only
create 9. The remaining 10 tables are created by `create_all()` at startup.

### Fresh Database Procedure

1. Start the application — `create_all()` creates all 19 tables
2. Run `alembic stamp head` to mark migrations as applied
3. Future migrations can then be run with `alembic upgrade head`

### Existing Database Adoption (Production)

For databases created by `create_all()` before Alembic was integrated:

1. **Verify schema** — `create_all()` produces the complete ORM schema,
   which is a superset of what migrations 001-004 create
2. **Stamp head** — `alembic stamp head` marks all migrations as applied
3. **No data loss** — stamping does not modify data or schema

```bash
# One-time operation on existing production database
alembic -c enterprise/alembic.ini stamp head
```

**Safety:** Verified that ORM schema is a superset of migration schema.
All columns added by migrations 002-004 already exist in ORM models.

### Explicit Migration Step (Recommended)

Migrations should be an explicit deployment step, not automatic startup:

```bash
# During deployment
alembic -c enterprise/alembic.ini upgrade head
```

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
