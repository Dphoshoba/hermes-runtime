#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-/Users/david/EVOS}"
OUTPUT_DIR="${2:-./hermes-report}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
python3 -m hermes_v01 --repo "$REPO" --output-dir "$OUTPUT_DIR"
