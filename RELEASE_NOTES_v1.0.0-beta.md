# Release Notes — Hermes Runtime v1.0.0-beta

**Version:** 1.0.0b0
**Date:** 2026-08-09
**Status:** Beta — Ready for external validation

## What Is This?

Hermes Runtime is an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring. It is designed for deterministic, restart-safe operation with full audit trails.

## What's New in This Release

### Multi-Language Scanning

Hermes now supports **Python** and **JavaScript/TypeScript** repositories:

- **File extensions:** `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`
- **Manifest detection:** `pyproject.toml`, `package.json`, `tsconfig.json`
- **Framework detection:** React, Vue, Angular, Svelte, Next, Nuxt, Express, Fastify, Django, Flask, FastAPI
- **JavaScript-specific analysis:**
  - React component detection (function components, hooks, memo, forwardRef)
  - Import/export parsing (ESM and CommonJS)
  - Dependency extraction from `package.json`
  - Configuration file detection (eslint, prettier, vite, webpack, etc.)
  - Complexity signals (large modules, high hook concentration, API concentration)
  - Debt signals (hardcoded credentials, missing tests, large components)

### Scanner Registry

A new `ScannerRegistry` abstraction enables pluggable language scanners:

- `RepositoryScanner` ABC with `detect()` and `scan()` interface
- Auto-detection of repository languages
- Multi-scanner result merging

### Critical Bug Fixes

- **PythonScanner.scan() circular recursion** — Fixed infinite recursion that caused 0 modules to be returned when scanning via the registry
- **Analyzer schema mismatches** — Fixed `KeyError` when analyzing JavaScript modules that use `file_path` instead of `path`
- **Import key mismatches** — Fixed `KeyError` when processing JavaScript imports that use `source` instead of `module`
- **Signal model field mismatches** — Fixed `TypeError` when converting scanner complexity/debt signals to model objects
- **JS scanner validation exclusion** — Added `validation/` directory exclusion to match Python scanner behavior

## Validated Architecture

| Subsystem | Status | Tests |
|-----------|--------|-------|
| Repository Intelligence | COMPLETE | 68 |
| Engineering Intelligence | COMPLETE | 57 |
| Engineering Governance | COMPLETE | 31 |
| Mission Recommendation | COMPLETE | 31 |
| Planner Integration | COMPLETE | 44 |
| Validation Program | COMPLETE | 32 |
| Beta Readiness | COMPLETE | 24 |
| **Total** | | **880** |

## Test Baseline

- **944 tests passing** (0 failures)
- **7 golden repositories validated** (requests, click, flask, fastapi, django, numpy, pandas)
- **Deterministic output verified** (CV = 0.0145)
- **64 dedicated JS/TS scanner tests** covering language detection, parsing, React, TypeScript, mixed repos, robustness, determinism, and zero-Python-findings acceptance criterion

## Benchmark Results

| Repository | Time | Files | Modules | Findings | Approved | Missions |
|------------|------|-------|---------|----------|----------|----------|
| Hermes | 0.67s | 107 | 107 | 527 | 325 | 50 |
| requests | 0.19s | 37 | 37 | 165 | 111 | 50 |
| click | 0.54s | 77 | 77 | 624 | 553 | 50 |
| flask | 0.35s | 83 | 83 | 560 | 460 | 50 |
| fastapi | 4.87s | 1136 | 1136 | 3567 | 1650 | 50 |
| django | 23.88s | 2918 | 2918 | 6790 | 2692 | 50 |
| numpy | 7.65s | 495 | 495 | 3052 | 2421 | 50 |
| pandas | 61.40s | 1512 | 1512 | 14981 | 10398 | 50 |

## Known Limitations

1. **Mission cap:** Limited to 50 missions per run for performance
2. **Static analysis:** No runtime behavior analysis
3. **Evidence quality:** Most findings have single evidence reference
4. **Memory metric:** Reports system RSS, not process-specific memory
5. **Governance confidence:** 13.26% (lower than other categories)

## CLI Commands

| Command | Description |
|---------|-------------|
| `hermes-validate` | Read-only repository inspection |
| `hermes-supervise` | Persistent execution supervisor |
| `hermes-status` | Canonical runtime state projection |
| `hermes-record` | Immutable evidence recorder |
| `hermes-review` | Independent review of execution records |
| `hermes-health` | Runtime health monitoring |
| `hermes-runtime` | Queue-driven pipeline orchestrator |
| `hermes-queue` | Work queue management |
| `hermes-metrics` | Runtime and queue metrics |
| `hermes-capabilities` | Plugin and executor management |
| `hermes-plan` | Mission planning and validation |
| `hermes-mission` | Mission execution and reporting |
| `hermes-repo` | Repository Intelligence scan/show |
| `hermes-engineering` | Engineering Intelligence scan/show |
| `hermes-governance` | Engineering Governance scan/show |
| `hermes-recommend` | Mission recommendation generate/approve/reject |
| `hermes-benchmark` | Benchmark run/compare/summary/trend/confidence |

**Total: 17 CLI entry points**

## Installation

```bash
pip install -e .
```

Requires Python >= 3.10.

## Quick Start

```bash
# Scan a Python repository
hermes-repo scan --repo /path/to/python-repo

# Scan a JavaScript/TypeScript repository
hermes-repo scan --repo /path/to/js-repo

# Run full pipeline
hermes-engineering scan --repo /path/to/repo
hermes-governance scan --repo /path/to/repo
hermes-recommend generate --repo /path/to/repo

# Execute a mission
hermes-plan validate mission.json
hermes-mission run mission.json \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo \
  --cwd /path/to/workspace
```

## External Validation Status

**VALIDATED AGAINST REAL-WORLD REPOSITORIES**

### InspireVoice Frontend (React/JavaScript)

| Metric | Result |
|--------|--------|
| Languages detected | JavaScript, TypeScript |
| React component | App.js (255 lines, 17 hooks) |
| Routes detected | / , /admin |
| Fetch/API calls | 5 |
| Config files | package.json, tailwind.config.js, postcss.config.js |
| Dependencies | react, react-dom, react-router-dom, react-toastify |
| Findings | 3 (2 complexity, 1 configuration) |
| Python false positives | 0 |

### Validation Fixtures

- **JS/React fixture** — 7 tests for language detection, parsing, React, frontend intelligence
- **TypeScript fixture** — Tests for interfaces, type aliases, typed functions, enums
- **Mixed Python/JS fixture** — Tests for multi-language detection and scanning

## Upgrade Notes

- **Breaking change:** None from alpha. API may change before 1.0.0.
- **Migration:** No migration required. Queue files from v1.0.0-alpha load without changes.
- **New dependencies:** None. Hermes remains dependency-free.
