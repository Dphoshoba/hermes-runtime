# Engineering Intelligence v1.0 — Implementation Plan

## Architecture Overview

Engineering Intelligence is a **reasoning layer** that consumes `RepositoryIntelligence` JSON and produces `EngineeringIntelligence` — evidence-based engineering recommendations. It never scans, never modifies, never enqueues.

```
RepositoryIntelligence.json
        │
        ▼
┌─────────────────────────────┐
│  Engineering Intelligence   │
│  engine (analyze_engineering)│
└─────────────────────────────┘
        │
        ▼
EngineeringIntelligence.json
EngineeringIntelligence.md
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `hermes_v01/engineering_intel_models.py` | 10 frozen dataclasses |
| `hermes_v01/engineering_analyzer.py` | Finding/recommendation/mission generation engine |
| `hermes_v01/engineering_renderer.py` | JSON + Markdown rendering |
| `hermes_v01/engineering_cli.py` | `hermes-engineering` CLI (scan/show/summary/findings/missions) |
| `tests/test_engineering_intelligence.py` | 40+ focused tests |
| `ENGINEERING_INTELLIGENCE_SCHEMA.md` | Schema documentation |

## Files to Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add `hermes-engineering` entry point |
| `CHANGELOG.md` | Add v1.0.0-alpha Engineering Intelligence section |
| `ROADMAP.md` | Mark Engineering Intelligence as complete |

---

## Data Model (10 Frozen Dataclasses)

### 1. EvidenceReference
Links every finding to specific Repository Intelligence data.
```python
@dataclass(frozen=True)
class EvidenceReference:
    source: str          # "complexity_signals", "debt_signals", "module_graph", "tests", "dependencies", "public_api"
    reference_path: str  # "hermes_v01/mission.py" or "hermes_v01/mission.py::MissionRunner"
    detail: str          # "Module has 814 lines"
```

### 2. AffectedComponent
Identifies what part of the repository is affected.
```python
@dataclass(frozen=True)
class AffectedComponent:
    component_type: str  # "module", "class", "function", "dependency", "configuration", "cli", "test"
    component_path: str  # "hermes_v01/mission.py"
    component_name: str  # "mission.py" or "MissionRunner"
```

### 3. Finding
A specific observation derived from repository evidence.
```python
@dataclass(frozen=True)
class Finding:
    finding_id: str                          # "FINDING-001" (deterministic, sequential)
    category: str                            # one of 15 categories
    severity: str                            # "info", "low", "medium", "high", "critical"
    confidence: float                        # 0.0–1.0
    title: str                               # "Import cycle between mission and mission_constraints"
    explanation: str                         # detailed reasoning
    evidence_references: tuple[EvidenceReference, ...]
    affected_components: tuple[AffectedComponent, ...]
```

### 4. PriorityScore
Quantified priority with documented scoring formula.
```python
@dataclass(frozen=True)
class PriorityScore:
    score: float         # 0.0–10.0, composite
    impact: float        # 0.0–10.0, how many modules / how critical
    confidence: float    # 0.0–1.0, from evidence strength
    severity: float      # 0.0–10.0, from signal severity
    scope: float         # 0.0–10.0, how widespread
    formula: str         # "0.4*impact + 0.2*confidence*10 + 0.25*severity + 0.15*scope"
```

### 5. ConfidenceScore
How confident we are, with basis and limitations.
```python
@dataclass(frozen=True)
class ConfidenceScore:
    score: float         # 0.0–1.0
    basis: str           # "multiple complexity signals converge"
    limitations: str     # "analysis based on AST only, no runtime data"
```

### 6. Recommendation
What should be done about a finding.
```python
@dataclass(frozen=True)
class Recommendation:
    finding_id: str
    recommendation: str
    rationale: str
    priority: PriorityScore
    estimated_effort: str    # "trivial", "small", "medium", "large", "xl"
    estimated_risk: str      # "none", "low", "medium", "high"
    expected_benefit: str
```

### 7. RiskAssessment
Repository-level risk.
```python
@dataclass(frozen=True)
class RiskAssessment:
    level: str             # "low", "moderate", "high", "critical"
    reasoning: str
    evidence: tuple[str, ...]
    mitigation: str
```

### 8. CandidateMission
A mission that could address findings (NOT enqueued).
```python
@dataclass(frozen=True)
class CandidateMission:
    mission_id: str
    title: str
    description: str
    objective: str
    affected_modules: tuple[str, ...]
    estimated_effort: str
    priority: PriorityScore
    risk: RiskAssessment
    prerequisites: tuple[str, ...]
    supporting_findings: tuple[str, ...]
    mission_type: str   # "repository_maintenance", "documentation_refresh", etc.
```

### 9. EngineeringSummary
Executive summary counts.
```python
@dataclass(frozen=True)
class EngineeringSummary:
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    total_recommendations: int
    total_candidate_missions: int
    overall_risk: str
    health_score: float    # 0.0–100.0, derived from findings
```

### 10. EngineeringIntelligence (top-level)
```python
class EngineeringIntelligence:  # NOT frozen (uses field(default_factory=...))
    schema_version: str = "1"
    repository: dict[str, Any]       # from RI
    findings: tuple[Finding, ...]
    recommendations: tuple[Recommendation, ...]
    candidate_missions: tuple[CandidateMission, ...]
    risk_assessment: RiskAssessment
    summary: EngineeringSummary
```

---

## Finding Categories (15)

| # | Category | Source in RI | Detection Rule |
|---|----------|-------------|----------------|
| 1 | Architecture | `module_graph.import_cycles` | Each cycle → finding |
| 2 | Coupling | `module_graph.highly_connected_modules` | Each highly connected module → finding |
| 3 | Complexity | `complexity_signals` | Each signal → finding (promote warning→medium, info→low) |
| 4 | Documentation | `technical_debt_signals[missing_docstring]` | Each → finding |
| 5 | Testing | `tests.modules_without_tests`, low test-to-module ratio | Each untested module → finding |
| 6 | Packaging | `dependencies.build_backend`, `configuration` | Missing build config, inconsistent versions |
| 7 | Configuration | `configuration` | Missing essential configs (pyproject.toml, .gitignore) |
| 8 | Dependencies | `dependencies` | Missing version pins, no dev/test deps |
| 9 | CLI | `public_api.cli_entry_points` | Undocumented CLI, inconsistent naming |
| 10 | Public API | `public_api.classes`, `public_api.functions` | Large public surface without docs |
| 11 | Performance | `complexity_signals[deep_nesting]`, `complexity_signals[complex_function]` | Deep nesting, large AST |
| 12 | Maintainability | `complexity_signals[large_module]`, `complexity_signals[large_class]`, `complexity_signals[many_methods]` | Size thresholds |
| 13 | Observability | `configuration` | No logging config, no metrics |
| 14 | Security Signals | `dependencies` | Unpinned deps, old patterns |
| 15 | Technical Debt | `technical_debt_signals` | All debt signals → findings |

---

## Priority Scoring Model

```
priority_score = 0.40 * impact + 0.20 * (confidence * 10) + 0.25 * severity_norm + 0.15 * scope
```

Where:
- **impact** (0–10): number of affected modules scaled logarithmically; critical path modules get +3
- **confidence** (0.0–1.0): multiple converging evidence refs → higher confidence
- **severity_norm** (0–10): critical=10, high=7.5, medium=5, low=2.5, info=1
- **scope** (0–10): how many categories/modules are affected

Effort mapping: score>8 → large, >6 → medium, >4 → small, else trivial

---

## Recommendation Engine Rules

For each finding, generate exactly one recommendation:

| Finding Category | Default Recommendation | Effort | Risk |
|-----------------|----------------------|--------|------|
| Architecture (cycle) | Break import cycle via dependency inversion | large | medium |
| Coupling | Decouple highly connected module | medium | low |
| Complexity | Refactor into smaller functions | medium | low |
| Documentation | Add docstrings | trivial | none |
| Testing | Add test coverage | medium | none |
| Packaging | Fix packaging configuration | small | low |
| Configuration | Add missing config files | trivial | none |
| Dependencies | Pin versions, audit dependencies | small | low |
| CLI | Document CLI entry points | trivial | none |
| Public API | Add API documentation | small | none |
| Performance | Optimize deep nesting / complex functions | medium | medium |
| Maintainability | Split large modules/classes | large | medium |
| Observability | Add logging/metrics | medium | low |
| Security Signals | Audit dependencies for vulnerabilities | small | low |
| Technical Debt | Address accumulated debt | varies | varies |

---

## Mission Recommendation Engine

Group related findings into candidate missions:

| Mission Type | Trigger Findings | Minimum Findings |
|-------------|-----------------|-----------------|
| `repository_maintenance` | Architecture, Coupling, Maintainability | ≥1 |
| `documentation_refresh` | Documentation, Public API, CLI | ≥1 |
| `testing_improvements` | Testing | ≥1 |
| `dependency_review` | Dependencies, Security Signals | ≥1 |
| `configuration_cleanup` | Configuration, Packaging | ≥1 |
| `architecture_cleanup` | Architecture, Coupling | ≥1+ cycle |
| `release_readiness` | Any critical/high | ≥1 critical/high |

Each mission gets:
- Unique `mission_id`: `"MISSION-001"` format
- `supporting_findings`: list of finding_ids
- `affected_modules`: union of affected modules from findings
- `prerequisites`: other missions that should complete first (e.g., testing before release)

---

## CLI Design

```
hermes-engineering --repo <path> --input <json_path> --output-dir <dir> <command>
```

Global args:
- `--repo` (default: `.`) — repository root
- `--input` (default: `<repo>/repo-intelligence/REPOSITORY_INTELLIGENCE.json`) — RI JSON path
- `--output-dir` (default: `<repo>/engineering-intelligence/`) — output directory

Commands:
- `scan` — consume RI JSON, generate Engineering Intelligence, save artifacts
- `show` — print canonical JSON from persisted EI
- `summary` — executive summary (Markdown to stdout)
- `findings` — grouped findings (by category)
- `missions` — candidate missions only

---

## Determinism

- Findings sorted by `(severity_desc, category, finding_id)`
- Recommendations sorted by `(priority_score_desc, finding_id)`
- Missions sorted by `(priority_score_desc, mission_id)`
- All IDs are sequential: `FINDING-001`, `REC-001`, `MISSION-001`
- No timestamps, no random values
- `json.dumps(sort_keys=True, ensure_ascii=False)`

---

## Test Plan (40+ tests)

### Finding Generation (8 tests)
- `test_finding_generation_from_complexity_signals`
- `test_finding_generation_from_debt_signals`
- `test_finding_generation_from_cycles`
- `test_finding_generation_from_untested_modules`
- `test_finding_has_unique_id`
- `test_finding_has_evidence_references`
- `test_finding_has_affected_components`
- `test_no_finding_without_evidence`

### Recommendation Generation (6 tests)
- `test_recommendation_for_each_finding`
- `test_recommendation_priority_scoring`
- `test_recommendation_effort_mapping`
- `test_recommendation_risk_assessment`
- `test_recommendation_rationale`

### Mission Recommendation (6 tests)
- `test_candidate_mission_from_findings`
- `test_mission_groups_related_findings`
- `test_mission_has_prerequisites`
- `test_mission_does_not_enqueue`
- `test_mission_type_assignment`
- `test_mission_affected_modules`

### Severity & Confidence (5 tests)
- `test_severity_mapping_from_signals`
- `test_confidence_from_multiple_evidence`
- `test_confidence_from_single_evidence`
- `test_priority_score_formula`
- `test_health_score_calculation`

### Evidence References (4 tests)
- `test_every_finding_has_evidence`
- `test_evidence_references_ri_data`
- `test_no_fabricated_evidence`
- `test_evidence_paths_valid`

### Grouping & Rendering (5 tests)
- `test_findings_grouped_by_category`
- `test_markdown_has_all_sections`
- `test_markdown_renders_from_json_model`
- `test_json_roundtrip`
- `test_json_deterministic`

### CLI (5 tests)
- `test_cli_scan`
- `test_cli_show`
- `test_cli_summary`
- `test_cli_findings`
- `test_cli_missions`

### Malformed Input (3 tests)
- `test_malformed_ri_json`
- `test_empty_ri_json`
- `test_missing_required_fields`

### EVOSIA Self-Analysis (4 tests)
- `test_hermes_self_analysis`
- `test_hermes_findings_correspond_to_ri`
- `test_hermes_no_fabricated_findings`
- `test_hermes_deterministic`

---

## Execution Order

1. `engineering_intel_models.py` — dataclasses first (no dependencies)
2. `engineering_analyzer.py` — engine (depends on models + RI models)
3. `engineering_renderer.py` — rendering (depends on models)
4. `engineering_cli.py` — CLI (depends on analyzer + renderer)
5. `pyproject.toml` — register entry point
6. `tests/test_engineering_intelligence.py` — all tests
7. Run tests, fix issues
8. Dogfood against EVOSIA self-scan
9. Schema documentation
10. Changelog/roadmap updates
11. Full regression
12. Commit
