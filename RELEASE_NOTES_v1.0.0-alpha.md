# Release Notes — Hermes Runtime v1.0.0-alpha

**Version:** 1.0.0a0
**Date:** 2026-08-08
**Status:** Alpha — API may change before 1.0.0

## What Is This?

Hermes Runtime is an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring. It is designed for deterministic, restart-safe operation with full audit trails.

## Highlights

- **12 CLI commands** covering validation, supervision, evidence recording, review, health, runtime orchestration, queue management, metrics, capabilities, mission planning, and mission execution
- **Concurrent mission execution** via ThreadPoolExecutor with dependency-aware dispatch
- **Full lifecycle control** — pause, resume, cancel, abort running missions from a separate process
- **Deterministic reports** — JSON and Markdown generated from a single canonical model with stable key ordering
- **7 built-in mission types** — repository-maintenance, dependency-upgrade, documentation-refresh, security-audit, performance-audit, release-preparation, ci-verification
- **7 constraint types** — capability, version, repository, working directory, resource limit, execution window, dependency policy
- **593 tests passing** across 12 test files

## Installation

```bash
pip install -e .
```

Requires Python >= 3.10.

## Quick Start

```bash
# Plan a mission
hermes-plan validate mission.json
hermes-plan build mission.json --output plan.json

# Execute
hermes-mission run mission.json \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo \
  --cwd /path/to/workspace

# Check status
hermes-mission status --runtime-root "$HOME/.hermes/runtime"

# Generate report
hermes-mission generate-report <mission-id> --runtime-root "$HOME/.hermes/runtime"
```

## What's New in This Release

- Version bumped to 1.0.0a0 (PEP 440 alpha)
- Added MIT LICENSE file
- Improved package metadata (authors, classifiers)
- Decoupled module dependencies (reviewer no longer imports from evidence)
- Shared `atomic_write_json` utility
- Removed stale egg-info and unused imports

## Breaking Changes

None — this is the first alpha release. API may change before 1.0.0.

## Known Issues

- CLI handler type annotations incomplete (33 handlers use untyped `args`)
- No `py.typed` marker for downstream type checkers
- JSON schemas not included as package data

## Next Steps

- Complete type annotation coverage
- Deduplicate inline atomic_write_json copies
- Add `py.typed` and `package-data` to pyproject.toml
- Stabilize API for 1.0.0-beta
