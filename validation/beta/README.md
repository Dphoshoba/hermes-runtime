# Beta Deployment Documentation

This directory documents the Hermes hosted beta and desktop distribution.

## Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| M0 Baseline | PASS | 1419 backend tests, invariants held |
| M1 Threat Model | DONE | `M1_THREAT_MODEL.md` |
| M2 Tenant Isolation | IN PROGRESS | Code changes required |
| M3 Invite-Only Auth | IN PROGRESS | Code changes required |
| M4 GitHub App | OPERATOR ACTION REQUIRED | See below |
| M5 Demo Project | IN PROGRESS | Code changes required |
| M6 Ephemeral Repo | DOCUMENTED | `M6_EPHEMERAL_REPO_ISOLATION.md` |
| M7 PostgreSQL | SUPPORTED | Via `HERMES_DATABASE_URL` env var |
| M8 Secrets | DOCUMENTED | `M8_SECRETS.md` |
| M9 Dockerfile | DONE | `Dockerfile` |
| M10-M16 Hosted Deployment | OPERATOR ACTION REQUIRED | See below |
| M17-M23 Desktop Track | OPERATOR ACTION REQUIRED | See below |

## Operator Checkpoints

The following milestones require operator action (credentials, account
registration, or explicit approval). They are consolidated here to avoid
repeated interruptions.

### GitHub App Registration (M4)

Operator must:
1. Register a GitHub App under their account/organization.
2. Set callback URL: `https://<beta-domain>/api/auth/github/callback`.
3. Grant permissions: Metadata (read), Contents (read).
4. Generate a private key.
5. Note the App ID, Client ID.
6. Provide these to Hermes via Secret Manager.

### Cloud Deployment (M10)

Operator must:
1. Create a dedicated GCP project (`hermes-beta`).
2. Enable Cloud Run, Artifact Registry, Cloud SQL, Secret Manager.
3. Provision Cloud SQL PostgreSQL instance.
4. Provide billing account.

### Apple Signing (M19)

Operator must:
1. Have an Apple Developer account.
2. Provide signing certificate and notarization credentials.
3. OR accept that macOS build will be unsigned (testers must bypass Gatekeeper).

## Architecture

See `M1_THREAT_MODEL.md` for trust boundaries.

## Authority Model

All beta deployments preserve the Evidence & Risk Gate:
- AUTONOMOUS_MISSION_EXECUTION = DISABLED
- TARGET_REPOSITORY_MUTATION = DISABLED
- unsafe_automation_rate = 0.0
