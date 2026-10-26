"""Fail-closed container startup for SQLite-backed deployments."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if os.environ.get("EVOSIA_ENV", "production").lower() != "development":
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("verify_sqlite_backup.py"))],
            cwd=APP_ROOT,
            check=True,
        )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "enterprise/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=APP_ROOT,
        check=True,
    )

    port = os.environ.get("PORT", "8000")
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "enterprise.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()
