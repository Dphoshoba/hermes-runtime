from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reviewer import IndependentReviewer


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review one immutable Hermes execution record without modifying it"
    )
    parser.add_argument("--record", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    result = IndependentReviewer(Path(args.output_dir)).review(Path(args.record))
    print(json.dumps(result.envelope.as_dict(), indent=2, sort_keys=True))
    print(result.review_json_path)
    print(result.review_markdown_path)
    if result.envelope.outcome == "REVIEW_PASSED":
        return 0
    if result.envelope.outcome == "REVIEW_INCOMPLETE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
