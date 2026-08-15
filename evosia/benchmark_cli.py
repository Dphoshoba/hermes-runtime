"""hermes-benchmark CLI — Benchmarking and validation commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_config(args: argparse.Namespace) -> dict:
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(json.dumps({"error": f"Config not found: {config_path}"}), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def cmd_run(args: argparse.Namespace) -> int:
    """Run benchmark against a repository or all configured repositories."""
    from .benchmark_engine import run_benchmark, save_snapshot, Snapshot

    config = _load_config(args)
    snapshots_dir = Path(config.get("snapshots_dir", "validation/snapshots")).expanduser().resolve()

    if args.repo:
        # Single repository benchmark
        repo_path = Path(args.repo).expanduser().resolve()
        if not repo_path.is_dir():
            print(json.dumps({"error": f"Repository not found: {repo_path}"}), file=sys.stderr)
            return 1
        result = run_benchmark(str(repo_path))
        snapshot = Snapshot(
            snapshot_id=f"bench-{result.repository_name}-{result.timestamp.replace(':', '-').replace('T', '-').replace('Z', '')}",
            timestamp=result.timestamp,
            repository_name=result.repository_name,
            result=result,
            findings_summary={"total": result.findings_generated},
            missions_summary={"total": result.missions_generated},
            engineering_health=0.0,
        )
        path = save_snapshot(snapshot, snapshots_dir)
        print(json.dumps({
            "status": "completed", "repository": result.repository_name,
            "snapshot": str(path), **result.as_dict(),
        }, indent=2, sort_keys=True))
    else:
        # Benchmark all configured repos
        results = []
        benchmarks = config.get("benchmarks", {})
        for name, bench_config in benchmarks.items():
            print(f"Benchmarking {name}...", file=sys.stderr)
            repo_url = bench_config.get("repo_url", "")
            # Check if repo exists locally
            local_path = Path(f"validation/golden_repositories/{name}").expanduser().resolve()
            if local_path.is_dir():
                result = run_benchmark(str(local_path), repo_url)
                results.append(result)
            else:
                print(f"  Skipping {name}: not cloned locally", file=sys.stderr)
        print(json.dumps({
            "status": "completed", "benchmarked": len(results),
            "results": [r.as_dict() for r in results],
        }, indent=2, sort_keys=True))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two benchmark snapshots."""
    from .benchmark_engine import load_snapshots, compare_benchmarks
    snapshots_dir = Path(args.snapshots_dir).expanduser().resolve()
    snapshots = load_snapshots(snapshots_dir)
    if len(snapshots) < 2:
        print(json.dumps({"error": "Need at least 2 snapshots to compare"}), file=sys.stderr)
        return 1
    baseline = snapshots[-2]
    current = snapshots[-1]
    comparison = compare_benchmarks(baseline.result, current.result)
    print(json.dumps(comparison.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Show summary of all benchmark results."""
    from .benchmark_engine import load_snapshots, compute_summary
    snapshots_dir = Path(args.snapshots_dir).expanduser().resolve()
    snapshots = load_snapshots(snapshots_dir)
    results = [s.result for s in snapshots]
    summary = compute_summary(results)
    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    """Show trend analysis across snapshots."""
    from .benchmark_engine import load_snapshots, compute_trend
    snapshots_dir = Path(args.snapshots_dir).expanduser().resolve()
    snapshots = load_snapshots(snapshots_dir)
    trend = compute_trend(snapshots)
    print(json.dumps({"trend": [t.as_dict() for t in trend], "total_points": len(trend)}, indent=2, sort_keys=True))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate comprehensive benchmark report."""
    from .benchmark_engine import load_snapshots, compute_summary, compute_confidence
    snapshots_dir = Path(args.snapshots_dir).expanduser().resolve()
    snapshots = load_snapshots(snapshots_dir)
    results = [s.result for s in snapshots]
    summary = compute_summary(results)
    confidence = compute_confidence(results, snapshots)

    report = {
        "summary": summary.as_dict(),
        "confidence": confidence.as_dict(),
        "repositories_benchmarked": len(results),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_confidence(args: argparse.Namespace) -> int:
    """Generate engineering confidence report."""
    from .benchmark_engine import load_snapshots, compute_confidence
    snapshots_dir = Path(args.snapshots_dir).expanduser().resolve()
    snapshots = load_snapshots(snapshots_dir)
    results = [s.result for s in snapshots]
    confidence = compute_confidence(results, snapshots)
    print(json.dumps(confidence.as_dict(), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EVOSIA Benchmark Engine")
    parser.add_argument("--config", default="validation/benchmark_config.json")
    parser.add_argument("--snapshots-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--repo", default=None, help="Path to a single repository")

    sub.add_parser("compare")
    sub.add_parser("summary")
    sub.add_parser("trend")
    sub.add_parser("report")
    sub.add_parser("confidence")

    args = parser.parse_args()

    # Default snapshots dir from config if not provided
    if args.snapshots_dir is None:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        args.snapshots_dir = config.get("snapshots_dir", "validation/snapshots")

    handlers = {
        "run": cmd_run, "compare": cmd_compare, "summary": cmd_summary,
        "trend": cmd_trend, "report": cmd_report, "confidence": cmd_confidence,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
