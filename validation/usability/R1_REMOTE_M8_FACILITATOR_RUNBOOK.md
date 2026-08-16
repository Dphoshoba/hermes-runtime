# R1 Remote M8 — Facilitator Runbook

Operational runbook for the remote single-participant M8 session lifecycle.

## Prerequisites (one-time)

```bash
cd <repo>
cp .env.example .ev
# Edit .ev: set EVOSIA_JWT_SECRET (long random), EVOSIA_CORS_ALLOW_ORIGINS (your HTTPS origin), M8_HTTPS_PORT
# For a LOCAL operator smoke test only, generate self-signed certs:
bash scripts/generate-certs.sh
```

## Build & start the stack

```bash
docker-compose build
docker-compose up -d
docker-compose ps
```

The stack exposes:
- backend (internal only, not published to host)
- nginx on `M8_HTTPS_PORT` (default 443), terminating HTTPS

## Per-session facilitator lifecycle

### 1. Prepare environment (RESET → SEED → VERIFY)

```bash
docker-compose exec backend python -m enterprise.cli_m8_fixture reset --confirm
docker-compose exec backend python -m enterprise.cli_m8_fixture seed --confirm
docker-compose exec backend python -m enterprise.cli_m8_fixture verify --confirm
```

### 2. Capture pre-session integrity

```bash
git -C validation/m8-disposable-repo rev-parse HEAD
# Record this hash. It must be identical post-session.
```

### 3. Create/confirm participant authentication

The fixture pre-creates `m8-participant@example.com`. Register a dedicated
participant via the web UI login page, or create one server-side:

```bash
# inside container: register a participant account
docker-compose exec backend python -c "
from enterprise.database import SessionLocal
from enterprise.models import User
from enterprise.services import hash_password
db = SessionLocal()
db.add(User(email='m8-participant@example.com', name='M8 Participant', hashed_password=hash_password('m8-participant-password')))
db.commit()
print('participant ready')
"
```

Provide the participant their HTTPS URL + credentials via a separate channel.

### 4. Participant performs M8

Facilitator observes via consented screen-share / video call (outside EVOSIA).
Do not explain controls, Git, Prepare, Approve, or the answers.

### 5. Post-session integrity

```bash
git -C validation/m8-disposable-repo rev-parse HEAD
# Must equal pre-session hash. Also confirm target config.py unchanged.
```

### 6. Record observation

Write the participant record to `validation/usability/participants/Pnn.json`
from observed evidence only. Do not fabricate.

### 7. Terminate participant access + RESET

```bash
# Revoke access by removing the participant's credentials / changing secrets:
docker-compose exec backend python -c "
from enterprise.database import SessionLocal
from enterprise.models import User
db = SessionLocal()
db.query(User).filter(User.email=='m8-participant@example.com').delete()
db.commit()
print('participant revoked')
"
docker-compose exec backend python -m enterprise.cli_m8_fixture reset --confirm
```

## Tear down the stack (optional)

```bash
docker-compose down -v
```

## Security notes

- All secrets live in `.ev` (never committed) and the container env.
- No secret appears in the frontend bundle (verified by `scripts/check-secrets.sh`).
- CORS is locked to the single `EVOSIA_CORS_ALLOW_ORIGINS` origin; no wildcard+credentials.
- JWT fail-closed active in `production` mode.
- Preparation workspace is isolated (target repo never mutated; candidate only in `/app/prep_workspaces`).
- `EVOSIA_M8_FIXTURE` gates seed/reset/verify — they are NOT public endpoints.
- Participants only ever see the EVOSIA web application; no admin/server access.
