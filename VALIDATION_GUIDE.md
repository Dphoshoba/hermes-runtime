# Validation Guide

## Overview

This guide explains how to validate Hermes against real-world repositories using the benchmark engine and golden validation datasets.

## Validation Process

### 1. Clone Golden Repositories

```bash
bash validation/clone_golden_repos.sh
```

This clones 7 public Python repositories for benchmarking:
- requests
- click
- flask
- fastapi
- django
- numpy
- pandas

### 2. Run Benchmarks

Benchmark all golden repositories:

```bash
hermes-benchmark run
```

Benchmark a specific repository:

```bash
hermes-benchmark run --repo validation/golden_repositories/requests
```

### 3. Validate Against Expectations

Each golden repository has expected minimums defined in `validation/benchmark_config.json`.

Hermes validates:
- Minimum modules discovered
- Minimum findings generated
- Pipeline completes without errors
- Output is deterministic

### 4. Compare Results

Compare current benchmark against previous:

```bash
hermes-benchmark compare
```

This identifies regressions and improvements.

### 5. Track Trends

View longitudinal analysis:

```bash
hermes-benchmark trend
```

### 6. Generate Confidence Report

```bash
hermes-benchmark confidence
```

Confidence scores derive from measurable evidence:
- Module-to-file coverage ratio
- Findings per module density
- Governance approval rate
- Mission generation rate
- Determinism coefficient

## Golden Validation Datasets

Each repository includes expected outputs:

### Expected Findings

Minimum number of engineering findings Hermes should identify.

### Expected Missions

Minimum number of missions Hermes should generate.

### Expected Summary

Human-readable summary of expected behavior.

## Drift Detection

The benchmark engine detects drift by comparing:
- Findings count changes
- Mission count changes
- Architecture health changes
- Performance regressions

## Self-Validation

Hermes benchmarks itself to validate:
- All 856+ tests pass
- Pipeline completes end-to-end
- Deterministic output
- Engineering confidence is evidence-based

## Files

```
validation/
├── benchmark_config.json         # Repository configuration
├── clone_golden_repos.sh         # Clone script
├── golden_repositories/          # Cloned repositories
│   └── hermes-runtime.json       # Hermes self-validation dataset
├── snapshots/                    # Benchmark snapshots
└── benchmarks/                   # Generated reports
    ├── ENGINEERING_BENCHMARK.json
    └── ENGINEERING_CONFIDENCE.json
```

## Running Validation

### Full Validation

```bash
# 1. Clone repos
bash validation/clone_golden_repos.sh

# 2. Run benchmarks
hermes-benchmark run

# 3. Check results
hermes-benchmark summary

# 4. Generate confidence
hermes-benchmark confidence

# 5. Check for regressions
hermes-benchmark compare
```

### Quick Validation

```bash
# Benchmark Hermes itself
hermes-benchmark run --repo .

# Check confidence
hermes-benchmark confidence
```

## Interpreting Results

### Confidence Scores

- **0.0-0.3**: Low confidence — investigate
- **0.3-0.6**: Moderate confidence — acceptable for alpha
- **0.6-0.8**: High confidence — good for beta
- **0.8-1.0**: Very high confidence — production ready

### Determinism

- **CV < 0.01**: Highly deterministic
- **CV 0.01-0.05**: Acceptable determinism
- **CV > 0.05**: Investigate timing variance

### Regressions

- **Duration > 10% increase**: Performance regression
- **Memory > 20% increase**: Memory regression
- **Findings > 5 decrease**: Coverage regression
