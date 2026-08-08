# Benchmarking Guide

## Overview

Hermes includes a benchmark engine for measuring pipeline performance, validating correctness, and tracking engineering confidence over time.

## Quick Start

### Benchmark Hermes Itself

```bash
hermes-benchmark run --repo .
```

### Generate Summary

```bash
hermes-benchmark summary
```

### Generate Confidence Report

```bash
hermes-benchmark confidence
```

### Generate Full Report

```bash
hermes-benchmark report
```

## Commands

### `hermes-benchmark run`

Run the full Hermes pipeline against a repository and measure performance.

```bash
# Benchmark a single repository
hermes-benchmark run --repo /path/to/repo

# Benchmark all configured repositories
hermes-benchmark run
```

**Output includes:**
- Pipeline timing (scan, RI, EI, governance, mission generation)
- Peak memory usage
- Repository metrics (files, modules, functions, classes)
- Pipeline output (findings, recommendations, missions)

### `hermes-benchmark compare`

Compare two benchmark snapshots.

```bash
hermes-benchmark compare
```

**Identifies:**
- Duration regressions (>10% increase)
- Memory regressions (>20% increase)
- Finding count changes

### `hermes-benchmark summary`

Show summary statistics across all benchmark results.

```bash
hermes-benchmark summary
```

**Includes:**
- Total repositories benchmarked
- Average timing
- Average memory
- Determinism rate

### `hermes-benchmark trend`

Show trend analysis across snapshots.

```bash
hermes-benchmark trend
```

### `hermes-benchmark confidence`

Generate evidence-based engineering confidence scores.

```bash
hermes-benchmark confidence
```

**Confidence categories:**
- Repository Intelligence confidence: `min(1.0, modules_scanned / files_scanned)`
- Engineering Intelligence confidence: `min(1.0, findings_per_module / 3.0)`
- Governance confidence: `approved / total_recs`
- Recommendations confidence: `min(1.0, missions / approved)`
- Overall confidence: `0.25*RI + 0.30*EI + 0.25*Gov + 0.20*Rec`

### `hermes-benchmark report`

Generate comprehensive benchmark report with summary and confidence.

```bash
hermes-benchmark report
```

## Configuration

Edit `validation/benchmark_config.json` to configure repositories for benchmarking.

### Adding a Repository

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/user/my-project",
  "description": "My project description",
  "language": "python",
  "expected_modules_min": 5,
  "expected_findings_min": 3
}
```

### Golden Repositories

Clone golden repositories for benchmarking:

```bash
bash validation/clone_golden_repos.sh
```

## Metrics

### Timing Metrics
- **repo_scan_seconds**: Repository AST scanning time
- **ri_generation_seconds**: Repository Intelligence generation
- **ei_generation_seconds**: Engineering Intelligence generation
- **gov_generation_seconds**: Engineering Governance generation
- **mission_generation_seconds**: Mission Recommendation generation
- **total_pipeline_seconds**: End-to-end pipeline time

### Memory Metrics
- **peak_bytes**: Peak memory usage in bytes
- **peak_mb**: Peak memory usage in megabytes

### Repository Metrics
- **files_scanned**: Total files scanned
- **modules_scanned**: Python modules discovered
- **functions_scanned**: Functions discovered
- **classes_scanned**: Classes discovered
- **public_apis_scanned**: Public API entries

### Pipeline Output
- **findings_generated**: Engineering findings
- **recommendations_generated**: Recommendations
- **approved_recommendations**: Approved by governance
- **missions_generated**: Draft missions created
- **total_tasks**: Total tasks across all missions

## Determinism

Identical input should produce identical output. The benchmark engine measures determinism via:

- Coefficient of variation of pipeline duration
- Consistency of findings/missions counts across runs
- Byte-identical JSON output for same input

## Snapshot Storage

Snapshots are stored in `validation/snapshots/` as JSON files. Each snapshot includes:
- Full benchmark result
- Timestamp
- Repository metadata
- Findings and missions summary
