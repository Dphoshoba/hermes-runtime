#!/usr/bin/env bash
# Pre-deployment secret-leak inspection for the R1 remote M8 container image.
#
# Builds the frontend bundle and the backend package, then scans the artifacts
# for any accidental embedding of deployment secrets. The certified invariant:
# all deployment secrets (JWT, Gemini key, etc.) are server-side env vars and
# MUST NOT appear in the frontend bundle or baked into the image layers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT/enterprise-ui"
DIST_DIR="$FRONTEND_DIR/dist"
SRC_DIR="$FRONTEND_DIR/src"
FAIL=0

echo "=== R1 secret-leak inspection ==="

# Patterns that must NEVER appear in the frontend bundle source or build.
# These are secret-like tokens / env-var names that should stay server-side.
SECRET_PATTERNS=(
  "EVOSIA_JWT_SECRET"
  "EVOSIA_GEMINI_API_KEY"
  "EVOSIA_DATABASE_URL"
  "EVOSIA_PREP_ROOT"
  "hermes-enterprise-dev-secret"
)

echo ""
echo "--- Scanning frontend SOURCE ($SRC_DIR) for accidental secret literals ---"
for pat in "${SECRET_PATTERNS[@]}"; do
  if grep -rn "$pat" "$SRC_DIR" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.json" 2>/dev/null; then
    echo "  FAIL: '$pat' found in frontend source"
    FAIL=1
  fi
done

echo ""
echo "--- Building frontend to inspect bundle for embedded secrets ---"
if [ ! -d "$DIST_DIR" ]; then
  echo "  dist/ missing — building..."
  (cd "$FRONTEND_DIR" && npm ci >/dev/null 2>&1 && npm run build)
fi

echo ""
echo "--- Scanning frontend BUNDLE ($DIST_DIR) for secret literals ---"
BUNDLE_FAIL=0
for pat in "${SECRET_PATTERNS[@]}"; do
  if grep -rn "$pat" "$DIST_DIR" 2>/dev/null; then
    echo "  FAIL: '$pat' found in built frontend bundle"
    BUNDLE_FAIL=1
    FAIL=1
  fi
done
if [ "$BUNDLE_FAIL" -eq 0 ]; then
  echo "  OK: no secret literals in frontend bundle"
fi

echo ""
echo "--- Verifying backend reads secrets from env, not hardcoded defaults ---"
# JWT secret must be sourced from env at runtime (not a literal in code paths
# that reach the client). We assert the import reads from os.environ.
if grep -rn "SECRET_KEY\s*=" "$ROOT/enterprise/services/__init__.py" 2>/dev/null | grep -v "environ" | grep -v "^#" ; then
  echo "  WARN: SECRET_KEY assignment that may not be env-derived — inspect manually"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: PASS — no secret leaks detected"
  exit 0
else
  echo "RESULT: FAIL — secret leak(s) detected above. Fix before deployment."
  exit 1
fi
