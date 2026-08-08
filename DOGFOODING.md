# Hermes Dogfooding Guide

## Purpose

This directory contains the real-world validation framework for Hermes Runtime. The goal is to prove Hermes against real software engineering work and turn observed friction into evidence-based improvements.

## Structure

```
examples/missions/          # Representative mission definitions
  repo-maintenance.json     # Repository inspection and cleanup
  doc-refresh.json          # Documentation drift detection
  ci-verify.json            # CI/test verification
  dep-review.json           # Dependency review
  release-readiness.json    # Pre-release validation

validation/
  sample-repo/              # Isolated test repository for dogfooding
    src/__init__.py         # Minimal Python package
    tests/test_sample_app.py
    docs/api.md
    pyproject.toml
    requirements.txt        # Contains deliberate unused dependencies
```

## Running Dogfood Missions

### Prerequisites

```bash
cd /path/to/hermes-runtime
pip install -e .
cd validation/sample-repo
```

### Mission 1: Repository Maintenance

```bash
hermes-mission run ../../examples/missions/repo-maintenance.json \
  --runtime-root /tmp/hermes-dogfood/runtime \
  --repository . \
  --cwd .
```

### Mission 2: Documentation Refresh

```bash
hermes-mission run ../../examples/missions/doc-refresh.json \
  --runtime-root /tmp/hermes-dogfood/runtime \
  --repository . \
  --cwd .
```

### Mission 3: CI Verification

```bash
hermes-mission run ../../examples/missions/ci-verify.json \
  --runtime-root /tmp/hermes-dogfood/runtime \
  --repository . \
  --cwd .
```

### Mission 4: Dependency Review

```bash
hermes-mission run ../../examples/missions/dep-review.json \
  --runtime-root /tmp/hermes-dogfood/runtime \
  --repository . \
  --cwd .
```

### Mission 5: Release Readiness

```bash
hermes-mission run ../../examples/missions/release-readiness.json \
  --runtime-root /tmp/hermes-dogfood/runtime \
  --repository . \
  --cwd .
```

## Validating Mission Outcomes

After each mission, verify:

1. **Mission Report** — Check `reports/<mission-id>/MISSION_REPORT.json`
2. **Evidence** — Check evidence records under the runtime root
3. **Reviews** — Check independent review outcomes
4. **Repository Integrity** — Verify sample-repo is unchanged (where expected)

## Sample Repository Deliberate Issues

The sample repository includes these deliberate maintenance issues:

- `requirements.txt` lists 3 unused dependencies (requests, flask, numpy)
- No `.gitignore` file (pycache, etc. would be visible)
- Version is `0.3.1` (not `1.0.0`)

These are intentional dogfood targets, not bugs.
