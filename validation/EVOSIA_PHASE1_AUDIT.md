# EVOSIA Naming Migration — Phase 1 Audit Report

**Date:** 2026-08-15  
**Repository:** `/Users/david/Downloads/hermes-runtime-v0.3-runtime`  
**Canonical commit:** `82229d83f45dcd2477a4a4c267dd200af4da77c7`  
**Audit scope:** Complete repository inspection for all Hermes/Hermes/HERMES references

---

## 1. Summary

| Metric | Count |
|--------|-------|
| Total files with Hermes references (content) | ~115 meaningful files |
| Files with Hermes in filename | 116+ (including .venv, snapshots, DB) |
| **OUR_SYSTEM references** (rename to EVOSIA) | ~100 files, ~500+ references |
| **THIRD_PARTY_HERMES** references (preserve) | 0 — no external Nous Research Hermes Agent references found |
| **AMBIGUOUS** references (manual review) | ~15 files |
| Directories with Hermes in name | 4 (hermes_v01/, hermes_runtime_v01.egg-info/, .venv subdirs) |

**Key finding:** There are **zero** references to external Nous Research "Hermes Agent" in this repository. Every Hermes reference is to this project's own identity. This simplifies the migration substantially — no ambiguity between our identity and third-party Hermes Agent.

---

## 2. OUR_SYSTEM References (Should Become EVOSIA)

### 2.1 Package & Code (hermes_v01/)

The `hermes_v01/` directory is our core runtime package. Every module name, CLI description, docstring, and comment referencing Hermes should become EVOSIA.

**Files (74+):**

| Category | Examples |
|----------|----------|
| Core modules | `runtime.py`, `evidence.py`, `reviewer.py`, `health.py`, `mission.py`, `mission_runner.py`, `supervisor.py`, `work_queue.py` |
| CLI modules | `repo_cli.py`, `reviewer_cli.py`, `governance_cli.py`, `health_cli.py`, `engineering_cli.py`, `runtime_cli.py`, `status_cli.py`, `benchmark_cli.py`, `mission_runner_cli.py`, `journal_cli.py`, `metrics_cli.py`, `readiness_cli.py`, `work_queue_cli.py`, `evidence_cli.py`, `capabilities_cli.py`, `mission_recommendation_cli.py`, `github_cli.py`, `plan_cli.py`, `supervisor_cli.py` |
| Models | `mission_types.py`, `mission_constraints.py`, `mission_state.py`, `mission_report.py`, `mission_recommendation_models.py`, `governance_intel_models.py`, `repo_intel_models.py`, `engineering_intel_models.py`, `journal_models.py`, `repo_analyzer_models.py`, `engineering_intel_models.py` |
| Renderers | `mission_report.py`, `repo_renderer.py`, `engineering_renderer.py`, `governance_renderer.py`, `benchmark_engine.py`, `mission_recommendation_renderer.py` |
| Engines | `benchmark_engine.py`, `evidence_enrichment.py`, `evidence_enrichment_v2.py`, `repo_scanner.py`, `repo_analyzer.py`, `engineering_analyzer.py`, `governance_analyzer.py`, `python_scanner.py`, `js_scanner.py`, `scanner_registry.py`, `language_detector.py`, `capabilities.py`, `metrics.py` |
| State | `runtime_state.py` |
| Utils | `utils.py` |

**Sample references to rename:**
- `description="Hermes Repository Intelligence — static repository analysis"` → `EVOSIA Repository Intelligence`
- `description="Review one immutable Hermes execution record without modifying it"` → `EVOSIA execution record`
- `description="Hermes Engineering Governance"` → `EVOSIA Engineering Governance`
- `description="Generate a read-only Hermes runtime health report"` → `EVOSIA runtime health report`
- `description="Run one command through the Hermes evidence pipeline"` → `EVOSIA evidence pipeline`
- `description="Show the canonical Hermes runtime state"` → `EVOSIA runtime state`
- `description="Hermes Engineering Intelligence — evidence-based engineering recommendations"` → `EVOSIA Engineering Intelligence`
- `description="Hermes Capability Manager"` → `EVOSIA Capability Manager`
- `description="Hermes Autonomous Mission Runner"` → `EVOSIA Autonomous Mission Runner`
- `"# Hermes Runtime Metrics"` → `"# EVOSIA Runtime Metrics"`
- `"# Hermes Runtime Health"` → `"# EVOSIA Runtime Health"`
- Documentation strings throughout: "Hermes pipeline", "Hermes runtime", "Hermes mission", etc.

### 2.2 Enterprise Backend (enterprise/)

Our FastAPI backend references Hermes throughout.

| File | References |
|------|-----------|
| `enterprise/__init__.py` | `"Hermes Enterprise — Engineering Command Center backend."` |
| `enterprise/app.py` | `title="Hermes Engineering Command Center"`, `description="Observability platform for Hermes Enterprise"` |
| `enterprise/services/scanner.py` | `"Uses the Enterprise-Core bridge to invoke real Hermes Core pipeline stages."`, `"Execute real Hermes Core pipeline stages"` |
| `enterprise/services/hermes_core.py` | `"Enterprise → Hermes Core integration bridge."`, `"Orchestrates real Hermes Core pipeline stages for Enterprise scan jobs."` |
| `enterprise/routers/guided.py` | Multiple references — title, descriptions, summary text |

### 2.3 Tests (tests/)

Test files, conftest, fixtures reference Hermes extensively.

**Conftest.py:** `"Hermes Enterprise test configuration"`  
**Test files:** `test_engineering_intelligence.py`, `test_resilience.py`, `test_safety.py`, `test_mission_recommendations.py`, `test_engineering_governance.py`, `test_repo_intelligence.py`, `test_validation.py`, `test_e2e_flows.py`, `test_guided_mode_e2e.py`, `test_m9_artifact_validator.py`

Test content references: "Hermes pipeline", "Hermes health", "Hermes runtime", "Hermes Enterprise", etc.

### 2.4 Documentation

| File | References |
|------|-----------|
| `HERMES_MANUAL.md` (1169 lines) | Title, body, CLI references, architecture text — extensive |
| `HERMES_PHILOSOPHY.md` (381 lines) | Title, body, principles — extensive |
| `ARCHITECTURE.md` (463 lines) | Title, module listing — extensive |
| `EVIDENCE_ENRICHMENT_V1_REPORT.md` | "Hermes" in body text |
| `BETA_READINESS.md` | "Hermes" in body text |
| `ACCEPTANCE_CYCLE_1_REPORT.md` | "Hermes" in body text |
| `CONTROLLED_BETA_*_REPORT.md` (multiple) | "Hermes" in body text |
| `ARCHITECTURE_SNAPSHOT.md` | "Hermes" in body text |
| `BENCHMARKING.md` | "Hermes" in body text |
| `CHANGELOG.md` | "Hermes" in body text |
| `HERMES_ENTERPRISE_ARCHITECTURE.md` | Title + body |
| `architecture/HERMES_ENTERPRISE_ARCHITECTURE.md` | Title + body |

### 2.5 CLI Entry Points (.venv/bin/)

These are the pip-installed CLI executables for our package. They'll be regenerated when the package is renamed.

| Executable | Current Name | New Name |
|------------|-------------|----------|
| Repository validation | `hermes-validate` | `evosia-validate` |
| Record review | `hermes-review` | `evosia-review` |
| Runtime execution | `hermes-runtime` | `evosia-runtime` |
| Status check | `hermes-status` | `evosia-status` |
| Supervision | `hermes-supervise` | `evosia-supervise` |
| Health check | `hermes-health` | `evosia-health` |
| Record | `hermes-record` | `evosia-record` |

### 2.6 Database & State Files

| File | Current Name | Notes |
|------|-------------|-------|
| `enterprise/hermes_enterprise.db` | SQLite DB | Filename contains Hermes |
| `hermes_enterprise.db` (root) | SQLite DB | Filename contains Hermes |
| `hermes_runtime_v01.egg-info/` | Package metadata dir | Auto-generated by pip |
| `.venv/lib/python3.12/site-packages/__editable__.hermes_runtime_v01-0.1.0.pth` | Editable install path | Auto-generated |

### 2.7 Validation Artifacts

| File | Current Name | Notes |
|------|-------------|-------|
| `validation/snapshots/bench-hermes-runtime-v0.3-runtime-*.json` (70+ files) | Benchmark snapshots | Filenames contain Hermes |
| `validation/golden_repositories/hermes-runtime.json` | Golden dataset | Filename + content |
| `validation/sample-repositories/` | Sample repos | Directory name |

### 2.8 Configuration

| File | References |
|------|-----------|
| `pyproject.toml` | Package name `hermes-runtime-v01` |
| `env.template` | May contain HERMES_ vars |
| `.venv/lib/python3.12/site-packages/__editable___hermes_runtime_v01_0_1_0_finder.py` | Auto-generated |

---

## 3. THIRD_PARTY_HERMES References (Preserve)

**Count: 0**

No references to external Nous Research "Hermes Agent" were found in this repository. The project is entirely self-referential — every "Hermes" is this project's own identity.

If this project ever integrates with or references the actual Nous Research Hermes Agent (e.g., as a dependency, tool call target, or documented integration), those references must be preserved as "Hermes Agent" per the migration guardrails.

---

## 4. AMBIGUOUS References (Manual Review Required)

| File | Ambiguity |
|------|-----------|
| `validation/snapshots/bench-hermes-runtime-v0.3-runtime-*.json` (70+ files) | These are historical benchmark snapshots. The filename embeds the repo name. **Decision:** Rename directory to `evosia-runtime-v0.3-runtime/` and update all snapshot filenames. Historical records can note the former name. |
| `validation/golden_repositories/hermes-runtime.json` | Golden dataset for self-analysis. **Decision:** Rename to `evosia-runtime.json`. |
| `architecture/HERMES_ENTERPRISE_ARCHITECTURE.md` | Duplicate of root `HERMES_ENTERPRISE_ARCHITECTURE.md`. **Decision:** Confirm intent, rename both. |
| `enterprise/hermes_enterprise.db` + `hermes_enterprise.db` | SQLite databases. **Decision:** Rename to `evosia_enterprise.db`. If existing DB must be preserved for backward compat, old name can remain as alias. |

---

## 5. Files That Must Remain Unchanged

None identified — this repository is entirely self-referential.

If third-party Hermes Agent integration is added in the future, this section should be updated.

---

## 6. Identifiers That Could Affect Compatibility

### 6.1 Environment Variables

**`HERMES_DATABASE_URL`** — Used in:
- `enterprise/database.py` (default: `sqlite:///./hermes_enterprise.db`)
- Test configuration (`conftest.py`, various tests)
- `Dockerfile` (ENV declaration)
- Deployment config

**Impact if changed:** All existing deployments, test suites, and local development environments would break unless the variable is aliased.

**Recommendation:** Keep `HERMES_DATABASE_URL` as a supported alias during migration. Add `EVOSIA_DATABASE_URL` as the canonical name. Document both. Do not break existing setups.

### 6.2 Python Package Name

**Current:** `hermes_runtime_v01` (distribution name: `hermes-runtime-v01`)

**Impact if changed:** 
- `pip install hermes-runtime-v01` → `pip install evosia-runtime`
- All `import hermes_v01` statements need updating
- Entry point names change
- Editable install paths change

**Recommendation:** Renaming the package is a BREAKING CHANGE. If backward compatibility is required, publish the new package under a new name while keeping the old package available (or provide a compatibility shim). For this project's internal use, a clean rename is acceptable since all imports are within the repo.

### 6.3 CLI Command Names

**Current:** `hermes-validate`, `hermes-review`, `hermes-runtime`, `hermes-status`, `hermes-supervise`, `hermes-health`, `hermes-record`

**Impact if changed:** Any scripts or aliases using these commands break.

**Recommendation:** New names: `evosia-validate`, `evosia-review`, `evosia-runtime`, `evosia-status`, `evosia-supervise`, `evosia-health`, `evosia-record`. Document the rename.

### 6.4 FastAPI Route Prefix

**Current:** `/api/hermes/...` (if used)

**Impact if changed:** External API clients break.

**Recommendation:** Check all route prefixes. If `/api/hermes` is used, add `/api/evosia` as canonical and keep `/api/hermes` as a redirect/alias during migration.

### 6.5 Database Filename

**Current:** `hermes_enterprise.db`

**Impact if changed:** Existing database files won't be found if the app expects the new name.

**Recommendation:** Rename the DB file. If backward compat needed, support both filenames.

### 6.6 Repository Name

**Current:** `hermes-runtime-v0.3-runtime`

**Impact if changed:** Git remote URLs, clone paths, documentation references.

**Recommendation:** The repo directory name is a filesystem concern. Rename locally. Git remote URL may need updating if hosted.

---

## 7. Proposed Rename Mapping

| Current | New | Category |
|---------|-----|----------|
| `hermes_v01/` (package dir) | `evosia/` | Code |
| `hermes-runtime-v0.3-runtime/` (repo) | `evosia-runtime-v1.0/` | Repo |
| `HERMES_MANUAL.md` | `EVOSIA_MANUAL.md` | Doc |
| `HERMES_PHILOSOPHY.md` | `EVOSIA_PHILOSOPHY.md` | Doc |
| `ARCHITECTURE.md` (title: "Hermes Runtime Architecture") | `EVOSIA_ARCHITECTURE.md` (title: "EVOSIA Architecture") | Doc |
| `HERMES_ENTERPRISE_ARCHITECTURE.md` | `EVOSIA_ENTERPRISE_ARCHITECTURE.md` | Doc |
| `architecture/HERMES_ENTERPRISE_ARCHITECTURE.md` | `architecture/EVOSIA_ENTERPRISE_ARCHITECTURE.md` | Doc |
| `enterprise/hermes_enterprise.db` | `enterprise/evosia_enterprise.db` | Data |
| `hermes_enterprise.db` | `evosia_enterprise.db` | Data |
| `hermes_runtime_v01.egg-info/` | `evosia_runtime.egg-info/` | Build |
| `hermes-runtime-v01` (pip package) | `evosia-runtime` (pip package) | Package |
| `hermes-validate` (CLI) | `evosia-validate` (CLI) | CLI |
| `hermes-review` (CLI) | `evosia-review` (CLI) | CLI |
| `hermes-runtime` (CLI) | `evosia-runtime` (CLI) | CLI |
| `hermes-status` (CLI) | `evosia-status` (CLI) | CLI |
| `hermes-supervise` (CLI) | `evosia-supervise` (CLI) | CLI |
| `hermes-health` (CLI) | `evosia-health` (CLI) | CLI |
| `hermes-record` (CLI) | `evosia-record` (CLI) | CLI |
| `HERMES_DATABASE_URL` (env var) | `EVOSIA_DATABASE_URL` (canonical) + keep HERMES_ as alias | Config |
| `bench-hermes-runtime-v0.3-runtime-*.json` | `bench-evosia-runtime-v1.0-*.json` | Validation |
| `hermes-runtime.json` (golden) | `evosia-runtime.json` (golden) | Validation |
| All "Hermes" in code strings/docs | "EVOSIA" | Content |

**Preserve:** Any references to external Nous Research "Hermes Agent" (none currently exist).

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Package rename breaks pip installs | High | Publish under new name; keep old package available or provide compat shim |
| CLI command rename breaks scripts | Medium | Document new names; provide symlinks during transition |
| Env var rename breaks deployments | Medium | Support both `HERMES_DATABASE_URL` and `EVOSIA_DATABASE_URL` |
| Import path changes break code | High | Renaming `hermes_v01/` to `evosia/` requires updating all imports — do in one coordinated pass |
| Database filename change loses data | Medium | Rename the file, not the schema; if old DB must be preserved, copy/alias |
| Historical snapshot filenames | Low | Rename directory + files; historical records can note former name |
| Git remote URL changes | Low | Update remotes if repo is renamed |

---

## 9. Migration Complexity Assessment

**Estimated effort:** Medium-High

The migration is conceptually straightforward (find/replace "Hermes" → "EVOSIA") but has several coordination points:

1. **Package rename** (`hermes_v01/` → `evosia/`): Requires updating all intra-project imports. Largest single change.
2. **Documentation rewrite**: Manual.md (1169 lines), Philosophy.md (381 lines), Architecture.md (463 lines) + many smaller docs.
3. **CLI entry points**: Generated by setuptools from `pyproject.toml` — update entry point definitions.
4. **Test suite**: Tests reference Hermes extensively. All test content + conftest.
5. **Env var and config**: `HERMES_DATABASE_URL` throughout.
6. **Filenames**: ~70+ benchmark snapshots, golden dataset, DB files, doc files.
7. **Backend strings**: FastAPI title/description, router prefixes, service descriptions.

---

## 10. Proposed Migration Plan (Phase 2)

### Phase 2A — Preparation
1. Create `evosia/` directory alongside `hermes_v01/`
2. Copy all modules from `hermes_v01/` to `evosia/`, performing systematic rename
3. Update all intra-project imports from `hermes_v01` to `evosia`
4. Update `pyproject.toml` package name and entry points
5. Run full test suite — verify everything passes with new names

### Phase 2B — Documentation
1. Rename and rewrite `HERMES_MANUAL.md` → `EVOSIA_MANUAL.md`
2. Rename and rewrite `HERMES_PHILOSOPHY.md` → `EVOSIA_PHILOSOPHY.md`
3. Rename and rewrite `ARCHITECTURE.md` → `EVOSIA_ARCHITECTURE.md`
4. Rename `HERMES_ENTERPRISE_ARCHITECTURE.md` → `EVOSIA_ENTERPRISE_ARCHITECTURE.md`
5. Update all other documentation files (BETA_READINESS, ACCEPTANCE_CYCLE, CONTROLLED_BETA reports, etc.)
6. Update validation artifacts (benchmark snapshots directory, golden dataset)

### Phase 2C — Configuration & Infrastructure
1. Update `enterprise/database.py` to support `EVOSIA_DATABASE_URL` (canonical) with `HERMES_DATABASE_URL` as alias
2. Update `Dockerfile` ENV names
3. Rename `hermes_enterprise.db` → `evosia_enterprise.db` (or add alias support)
4. Update test configuration (`conftest.py`)

### Phase 2D — Cleanup
1. Remove old `hermes_v01/` directory (after verification)
2. Rename repo directory `hermes-runtime-v0.3-runtime/` → `evosia-runtime-v1.0/`
3. Update git remotes if applicable
4. Update any external references (README, deployment docs, etc.)

### Phase 2E — Verification
1. Full test suite: 1434/1434 PASS target
2. Frontend build: PASS
3. TypeScript: PASS
4. Manual spot-check of key UX surfaces (Guided Mode, review page, etc.)
5. Verify no Hermes references remain in our system files
6. Verify third-party Hermes Agent references (if any added) are preserved

---

## 11. Backward Compatibility Strategy

To minimize disruption:

1. **Environment variables:** Support both `HERMES_DATABASE_URL` and `EVOSIA_DATABASE_URL` during transition. `EVOSIA_DATABASE_URL` takes precedence if both set.

2. **Database files:** If `evosia_enterprise.db` doesn't exist, fall back to `hermes_enterprise.db`.

3. **Package:** If external consumers exist, keep `hermes-runtime-v01` published or provide a compatibility package that re-exports from `evosia-runtime`.

4. **CLI:** During transition, provide shell aliases: `hermes-validate` → `evosia-validate`, etc.

5. **API routes:** If `/api/hermes/` is used externally, keep as alias redirecting to `/api/evosia/`.

---

## 12. Recommendation

**Proceed to Phase 2 with the plan above.**

The audit confirms this is a clean rename — zero third-party Hermes Agent references, no ambiguous external dependencies. The primary complexity is coordination across package rename, imports, documentation, and configuration.

**Key decision points for operator approval:**

1. **Package rename scope:** Full rename (`hermes_v01/` → `evosia/`) vs. keeping internal package name and only changing user-facing identity strings.

2. **Env var strategy:** Break and rename `HERMES_DATABASE_URL` → `EVOSIA_DATABASE_URL`, or support both during transition.

3. **CLI command names:** Full rename to `evosia-*` or keep `hermes-*` as aliases.

4. **Database filename:** Rename or alias.

5. **Historical records:** Rename benchmark snapshots and golden datasets, or preserve original filenames with a note about the former name.

**Awaiting explicit approval before beginning Phase 2.**
