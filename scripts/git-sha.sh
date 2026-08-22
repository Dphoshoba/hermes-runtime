#!/usr/bin/env bash
# Emit the current git SHA for build provenance.
# Usage: GIT_SHA=$(bash scripts/git-sha.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
if git rev-parse HEAD >/dev/null 2>&1; then
  git rev-parse --short=7 HEAD
else
  echo "unknown"
fi
