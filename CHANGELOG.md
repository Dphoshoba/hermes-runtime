# Changelog

All notable changes to Hermes are documented here. This project adheres to
post-Cycle-8 Evidence & Risk Gate milestones.

## [Unreleased] — Evidence & Risk Gate (M-Cycle 8 Gate)

- Evidence & Risk Gate promoted as the Controlled Beta governance baseline; gate mode is now the default, legacy Governance remains replay-only, human `ACTIONABLE` adjudication controls mission eligibility, and autonomous mission execution/repository mutation remain disabled.

### Added
- **Evidence & Risk Gate** (`governance_intel_models.FindingGate`,
  `governance_analyzer.govern_engineering(mode="gate"|"legacy")`): machine
  authority emits `OBSERVED`/`CORROBORATED`/`REQUIRES_REVIEW`/
  `INSUFFICIENT_EVIDENCE`/`DEFERRED`/`DUPLICATE` — never `ACTIONABLE`/
  `NOT_ACTIONABLE`. Gate mode is the default Controlled Beta operating mode.
- `assert_machine_state()` guard: machine gate logic cannot emit human
  actionability states (frozen-dataclass `__post_init__` enforcement).
- **Hard mission authorization boundary** in `mission_generator.generate_missions`:
  a candidate mission is produced only for findings in `actionable_finding_ids`
  (human `ACTIONABLE` set). `approved_missions` is no longer the authorization
  path; `None` → no missions.
- **Human Review Service** extensions: `apply_deterministic_suppression`,
  `list_suppressions`; `FindingAdjudication` gains `policy_suppressed`,
  `suppression_rule_id`, `suppression_rule_version`. Deterministic suppression
  is distinct from human `NOT_ACTIONABLE` and fully auditable.
- API: `POST /review/findings/{id}/adjudications` accepts `ACTIONABLE`;
  `POST /review/findings/{id}/suppressions`, `GET /review/suppressions`.
- Journal events: `gate.evaluated`, `gate.routed`, `policy.suppression`,
  `human.adjudication`, `mission.eligibility`.
- CLI: `hermes-review` import path fixed; `classify` accepts `ACTIONABLE`;
  new `suppressions` subcommand.
- Metrics: `collect_gate_metrics` (replacement metrics); `governance_approval_rate`
  explicitly deprecated.
- Migration `004_evidence_risk_gate`: additive columns; historical
  `governance_decision` values never rewritten.
- Focused acceptance tests `tests/test_evidence_risk_gate.py` (A–J + M1–M6).

### Changed
- `MissionPrioritizer._GOVERNANCE_WEIGHTS` re-pointed from legacy `APPROVED` →
  human `ACTIONABLE`; `LEGACY_APPROVED` advisory (weight 0).
- `governance_renderer` distinguishes machine gate (NOT actionability) from
  human adjudication and legacy (advisory) decisions.
- `govern_engineering` default mode is now `gate` (was legacy auto-approval).

### Deprecated
- `governance_approval_rate` as a primary quality metric.
- Legacy automated `APPROVED` as mission authorization (use human adjudication).

### Safety
- No target repository mutated; no autonomous mission executed; no branch/PR.
- Historical Governance records immutable (new columns added, original
  `governance_decision` values untouched).
