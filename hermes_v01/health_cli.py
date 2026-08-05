from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .health import build_health_report, write_health_reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a read-only Hermes runtime health report"
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path.home() / ".hermes" / "runtime",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".hermes" / "runtime" / "health",
    )
    args = parser.parse_args()

    report = build_health_report(args.runtime_root)
    json_path, md_path = write_health_reports(report, args.output_dir)

    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
