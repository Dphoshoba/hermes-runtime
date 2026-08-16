"""Facilitator CLI for the M8 disposable fixture (test/dev/usability scoped).

Usage (must enable explicitly):

    export EVOSIA_DATABASE_URL=sqlite:///./evosia_enterprise.db
    export EVOSIA_M8_FIXTURE=enabled
    export EVOSIA_JWT_SECRET=***

    python -m enterprise.cli_m8_fixture seed
    python -m enterprise.cli_m8_fixture reset
    python -m enterprise.cli_m8_fixture verify

The fixture is gated behind EVOSIA_M8_FIXTURE=enabled so it can never silently
mutate a production database. There is NO unauthenticated HTTP seed endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Support both `python -m enterprise.cli_m8_fixture` and direct execution.
try:
    from enterprise.database import SessionLocal
    from enterprise.services.m8_fixture import (
        require_fixture_enabled,
        reset_m8_fixture,
        seed_m8_fixture,
        verify_m8_fixture,
    )
except ImportError:  # pragma: no cover - alternate import layout
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from enterprise.database import SessionLocal
    from enterprise.services.m8_fixture import (
        require_fixture_enabled,
        reset_m8_fixture,
        seed_m8_fixture,
        verify_m8_fixture,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="M8 disposable fixture manager (SEED/RESET/VERIFY)")
    parser.add_argument("action", choices=["seed", "reset", "verify"])
    parser.add_argument("--confirm", action="store_true", help="Required safety confirmation")
    args = parser.parse_args()

    try:
        require_fixture_enabled()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.action in ("seed", "reset") and not args.confirm:
        print("ERROR: seed/reset require --confirm.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if args.action in ("seed", "reset"):
            from enterprise.database import Base, get_engine
            # Ensure tables exist before seeding (idempotent).
            Base.metadata.create_all(bind=get_engine())
        if args.action == "seed":
            result = seed_m8_fixture(db)
        elif args.action == "reset":
            result = reset_m8_fixture(db)
        else:
            result = verify_m8_fixture(db)
    finally:
        db.close()

    print(json.dumps(result, indent=2, sort_keys=True))
    # verify returns a dict; treat absence of "status":"verified" as failure.
    if args.action == "verify" and result.get("status") != "verified":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
