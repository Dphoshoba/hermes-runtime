"""
Build provenance — identifies the exact build a participant is seeing.

Resolves the git SHA once at import from (in priority order):
  1. EVOSIA_BUILD_SHA env (baked into the container image at build time)
  2. local git metadata (development)
Falls back to "unknown" — never a fabricated value.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def build_sha() -> str:
    env = os.environ.get("EVOSIA_BUILD_SHA", "").strip()
    if env and env.lower() != "unknown":
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def provenance() -> dict[str, str]:
    sha = build_sha()
    return {
        "build_sha": sha,
        # A SHA is only "known" if it came from a real source; unknown is honest.
        "provenance": "LIVE_EVOSIA_EVIDENCE" if sha != "unknown" else "unknown",
    }
