# Evidence & Risk Gate — Promotion Readiness Report

**Status:** PROMOTED as Controlled Beta governance baseline (M-Cycle 8)
**Hermes version:** 1.3.0
**Promotion commit:** local commit on `main` (no push / no PR / no tag) — per safety constraints.
**Authorization:** Operator promotion decision — gate model only.

This document records the verified state at promotion time. It does **not**
rewrite historical reports; legacy data and reports remain as authored.

## Governance model promoted

```
DETECT
  → ENRICH
  → EVIDENCE & RISK GATE
  → HUMAN REVIEW
  → MISSION PRIORITIZATION
  → MISSION RECOMMENDATION
```

Not:

```
DETECT → MACHINE APPROVAL → MISSION
```

- **Default Governance mode = `GATE`** (machine observes, human adjudicates).
- **Legacy mode = explicit replay only** — `governance_analyzer(mode="legacy")`
  re-runs historical `APPROVED` decisions for comparison; it is never an
  authorization path.
- **Machine gate states are non-authoritative for actionability.** The machine
  emits `OBSERVED` / `CORROBORATED` / `REQUIRES_REVIEW` /
  `INSUFFICIENT_EVIDENCE` / `DEFERRED` / `DUPLICATE` — never `ACTIONABLE` /
  `NOT_ACTIONABLE` (enforced by the `FindingGate` frozen-dataclass
  `__post_init__` guard).
- **Human adjudication controls mission eligibility.** A candidate mission is
  produced only for findings in `actionable_finding_ids` (human `ACTIONABLE`).
- **MissionPrioritizer operates after human `ACTIONABLE`** — it ranks/defers
  `DraftMission` objects; it does not authorize actionability.
- **Mission approval remains a separate human authority boundary.**
- **Mission execution = DISABLED. Repository mutation = DISABLED.**

## Verification evidence (real execution)

| Gate | Result |
|------|--------|
| Backend canonical suite | **1434 / 1434 passed** (×2 repeat runs: 206.10s, 205.32s) |
| Targeted gate tests | 370 / 370 passed (§10B), 162 focused (§11A) |
| Frontend dependency install | `npm ci` — PASS |
| Frontend tests | **36 / 36 passed** (vitest) |
| TypeScript | `npx tsc --noEmit` — PASS |
| Frontend production build | `npm run build` — PASS (203 KB JS / 4.5 KB CSS) |
| Clean wheel install | PASS (disposable venv, no repo on PYTHONPATH) |
| Enterprise subpackages packaged | models / schemas / services / routers / migrations + versions 001–004 |
| Enterprise extras | fastapi, uvicorn, pydantic[email], sqlalchemy, alembic, python-jose, passlib, bcrypt |
| Wheel hygiene | 0 `__pycache__` / `.pyc` entries |
| Version consistency | pyproject 1.3.0 = wheel metadata 1.3.0 = `/api/health` 1.3.0 |
| Migration (packaged) | base → 004_evidence_risk_gate — PASS |
| ORM reopen | 10 tables; gate columns + `legacy_decision` present |
| API smoke | unauth write 401 / ACTIONABLE write 200 / suppression distinct |
| CLI smoke | `hermes-human-review --help` 0; `classify ACTIONABLE` succeeds |
| Journal integrity | PASS (defect found + fixed, re-verified) |
| Database reopen / reconstruction | PASS |

## Authority model — measured

| State | Machine gate | → Mission |
|-------|--------------|-----------|
| A. UNREVIEWED | `INSUFFICIENT_EVIDENCE` | **0** (blocked) |
| B. LEGACY APPROVED | `INSUFFICIENT_EVIDENCE` | **0** (blocked) |
| C. HUMAN NEEDS_MORE_EVIDENCE | n/a | **0** (blocked) |
| D. HUMAN NOT_ACTIONABLE | n/a | **0** (blocked) |
| E. HUMAN ACTIONABLE | n/a | **1 eligible** (DRAFT) |
| F. POLICY SUPPRESSED | n/a | **0** (blocked) |

- **`NO_HUMAN_ACTIONABLE = NO_MISSION` invariant: VERIFIED.**
- **`unsafe_automation_rate` = 0.0**
- **`mission_traceability` = 100%**
- **Mission execution = DISABLED**
- **Repository mutation = DISABLED**

## Historical data preserved (immutable)

- Trial 001 historical Governance decisions — unmodified.
- Cycle 7 frozen review dataset — unmodified.
- Historical journal events — unmodified; legacy `APPROVED` values retained as
  advisory-only `legacy_decision`.
- Historical human adjudications — unmodified.

## Defect register (all resolved during promotion verification)

| ID | Classification | Root cause | Fix | Verification | Status |
|----|----------------|------------|-----|--------------|--------|
| D1 | Performance remediation | `evidence_enrichment.analyze_engineering` fan-out: 2,489 git subprocess calls / 41.6 s | Single bounded git-log parse + LRU cache | 1.02 s / 1 call; governance + mission-rec tests pass | RESOLVED |
| D2 | Packaging dependency | `passlib` 1.7.4 incompatible with `bcrypt` 5.0.0 (hash-encoding contract) | Pin `bcrypt>=4.0.1,<5.0.0` in enterprise extras | test_enterprise 77 passed | RESOLVED |
| D3 | Journal event registration | 5 gate event types missing from `STAGE_CATEGORIES` | Add gate/human/policy/mission event categories (`journal_models`) | 98 journal tests; EVENT_TYPES=31 | RESOLVED |
| D4 | Test isolation | Stale `engine` import from `enterprise.database` across suites (SQLite contamination) | URL-keyed `get_engine()` + bound fixture metadata | 33→0 errors | RESOLVED |
| D5 | Benchmark snapshot contamination | 2 non-benchmark governance/trial JSON in `validation/snapshots/` | Relocate to `validation/trial_snapshots/` (no data mutation) | test_benchmark 32 passed | RESOLVED |
| D6 | Test contract migration | Legacy test expectations assumed machine `APPROVED` authorized missions | Migrate beta-readiness / planner tests to gate contract (no xfail/skip/weaken) | 1434/1434 | RESOLVED |
| D7 | Packaging subpackage defect | Explicit `packages=["hermes_v01","enterprise"]` omitted subpackages | Enumerate `enterprise.models/routers/schemas/services` + `migrations/**` data | Wheel contains all subpackages + versions 001–004 | RESOLVED |
| D8 | Packaging dependency | `pydantic[email]` (EmailStr) not declared | `pydantic[email]>=2.0` in enterprise extras | Clean wheel import of app/routers/schemas | RESOLVED |
| D9 | Journal integrity hash defect | `_emit_journal_event` hashed with 64-char `hashlib.sha256(json.dumps(sort_keys,default=str))` vs verifier's 16-char `_canonical_payload_sha256` | Route through `_canonical_payload_sha256` | policy.suppression integrity verified; 0 dup ids | RESOLVED |
| D10 | Wheel hygiene | Build captured `__pycache__`/`*.pyc` from source tree | `exclude-package-data` + clean source; rebuild | 0 pyc in wheel | RESOLVED |

Note: `eslint` is declared in `enterprise-ui` devDependencies but is **not
installable via the committed `package-lock.json`** (`npm run lint` →
`eslint: command not found`). Lint was therefore treated as NOT_DEFINED for
this gate (not a promotion blocker; the substantive frontend gates —
tests / typecheck / build — pass). Recommend resolving the lockfile in a
follow-up cycle.

## Operational status after promotion

- `CONTROLLED_BETA` = ACTIVE
- `GOVERNANCE_BASELINE` = `EVIDENCE_RISK_GATE`
- `DEFAULT_MODE` = `GATE`
- `LEGACY_MODE` = `EXPLICIT_REPLAY_ONLY`
- `AUTONOMOUS_MISSION_EXECUTION` = DISABLED
- `REPOSITORY_MUTATION` = DISABLED

## Next-cycle readiness (NOT executed)

Recommended scope for the first post-promotion acceptance cycle: small cohort
(2–3 repositories), read-only scans, mandatory human review, mission generation
only after `ACTIONABLE` adjudication, no mission execution, measure review
burden + human usefulness/actionability rates + mission eligibility/traceability;
`unsafe_automation_rate` must remain 0.
