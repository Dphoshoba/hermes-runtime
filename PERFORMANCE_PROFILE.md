# Performance Profile

**Date:** 2026-08-08
**Repository:** hermes-runtime-v0.3-runtime

## Pipeline Timings

| Phase | Time | Percentage |
|-------|------|------------|
| Repository Scan | 0.58s | 86.6% |
| RI Generation | 0.02s | 3.0% |
| EI Generation | 0.01s | 1.5% |
| Governance | 0.06s | 9.0% |
| Mission Generation | 0.00s | 0.1% |
| **Total** | **0.67s** | **100%** |

## Bottleneck Analysis

**Primary bottleneck:** Repository scanning (86.6% of pipeline time)

The scanner walks the directory tree, discovers Python files, and parses ASTs. For 107 files, this takes 0.58s.

**Secondary bottleneck:** Governance (9.0%)

Governance evaluates evidence quality, detects duplicates, and makes approval decisions. For 527 recommendations, this takes 0.06s.

## Memory Usage

- Peak RSS: System-level measurement (includes other processes)
- Process memory: Estimated < 50MB for typical repositories

## Scaling Characteristics

| Repository | Files | Time | Time/File |
|------------|-------|------|-----------|
| requests | 37 | 0.19s | 5.1ms |
| click | 77 | 0.54s | 7.0ms |
| flask | 83 | 0.35s | 4.2ms |
| fastapi | 1136 | 4.87s | 4.3ms |
| django | 2918 | 23.88s | 8.2ms |
| numpy | 495 | 7.65s | 15.5ms |
| pandas | 1512 | 61.40s | 40.6ms |

**Observation:** Time scales roughly linearly with file count, with some variance due to file size and complexity.

## Largest Outputs

| Repository | Findings | Recommendations | Missions |
|------------|----------|-----------------|----------|
| pandas | 14,981 | 14,981 | 50 |
| django | 6,790 | 6,790 | 50 |
| fastapi | 3,567 | 3,567 | 50 |
| numpy | 3,052 | 3,052 | 50 |
| click | 624 | 624 | 50 |
| flask | 560 | 560 | 50 |
| hermes | 527 | 527 | 50 |
| requests | 165 | 165 | 50 |

## Recommendation Density

| Repository | Findings/Module | Approved/Total |
|------------|-----------------|----------------|
| hermes | 4.9 | 62% |
| requests | 4.5 | 67% |
| click | 8.0 | 89% |
| flask | 6.7 | 82% |
| fastapi | 3.1 | 46% |
| django | 2.3 | 40% |
| numpy | 6.2 | 79% |
| pandas | 9.9 | 69% |

## Optimization Opportunities

1. **Parallel scanning:** Use multiprocessing for file discovery and AST parsing
2. **Incremental analysis:** Cache scan results for unchanged files
3. **Lazy loading:** Load modules on-demand rather than all at once
4. **Governance batching:** Process recommendations in batches

## Conclusion

EVOSIA processes typical Python repositories in under 1 second. Large repositories (1000+ files) may take 5-60 seconds. The primary bottleneck is repository scanning, which could be optimized with parallel processing.
