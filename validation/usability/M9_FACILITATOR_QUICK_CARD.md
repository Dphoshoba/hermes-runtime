# M9 Facilitator Quick Card

## SAY ONLY THIS

> "EVOSIA has reviewed this project. Work out whether anything needs your
> attention and decide what you want EVOSIA to prepare."

## DO NOT

- explain the interface
- explain Git / repositories / branches / commits
- explain EVOSIA governance (gate states, mission eligibility, journal)
- point at buttons or features
- explain what "Prepare" or "Approve" means
- correct misunderstandings during the task unless safety requires it
- lead the participant toward any answer

## DO

- record where the participant hesitates
- record every question they ask
- record every intervention you make
- record technical terminology that confuses them
- record exact Task 9 and Task 10 responses verbatim

## Tasks

| # | Task |
|---|------|
| 1 | Open EVOSIA |
| 2 | Select a project |
| 3 | Start analysis |
| 4 | Explain what EVOSIA found |
| 5 | Respond to one context question |
| 6 | Inspect one recommendation |
| 7 | Inspect one prepared change |
| 8 | Decide whether to approve |
| 9 | **"Has EVOSIA changed your project?"** |
| 10 | **"What would happen if you approved?"** |

## Final Questions

9. "Has EVOSIA changed your project?"
10. "What would happen if you approved?"

**Do not lead the participant toward an answer.**

## Critical Gate

- Task 9 must be answered **No** (or equivalent).
- Task 10 must **not** imply deployment/execution.

Any failure = AUTHORITY_UX_DEFECT → remediate before future execution authority.

## M8 Disposable Fixture (Facilitator Setup)

The guided-mode fixture is a deterministic, resettable, disposable test repository.
It must be seeded into the REAL enterprise backend before Participant 01 starts.

**Prerequisites** (one-time, per machine):

```bash
cd <repo>/enterprise
export EVOSIA_DATABASE_URL=sqlite:///../evosia_enterprise.db
export EVOSIA_JWT_SECRET=<a-long-random-secret>
export EVOSIA_M8_FIXTURE=enabled        # required gate; never set in production
export EVOSIA_PREP_ROOT=<writable-temp-dir>   # isolated workspace root (optional)
```

**SEED / RESET** (identical — both produce the same deterministic starting state):

```bash
python -m enterprise.cli_m8_fixture seed --confirm
python -m enterprise.cli_m8_fixture reset --confirm
```

**VERIFY** (assert the fixture contains the required evidence):

```bash
python -m enterprise.cli_m8_fixture verify --confirm
```

The fixture contains, deterministically:
- 1 security finding flagged "worth discussing" (needs your attention)
- 3 context questions (large/complex areas, dependency choices, configuration setup)
- 1 DRAFT proposed change (replace hardcoded API key with environment configuration)
- a disposable on-disk repo with NO real secrets (fake placeholder credential only)

**Start the participant environment:**

```bash
# Backend (real EVOSIA — LIVE_MODE, not demo):
cd <repo>/enterprise && uvicorn enterprise.app:app --port 8000 &
# Frontend:
cd <repo>/enterprise-ui && npm run dev
# Open the UI; confirm the provenance badge shows LIVE_EVOSIA_EVIDENCE.
```

**Between participants:** run RESET then SEED to restore the canonical starting state.

> The fixture is test/dev/usability-scoped only. SEED/RESET/VERIFY refuse to run
> unless `EVOSIA_M8_FIXTURE=enabled`. Do NOT run against a production database.
