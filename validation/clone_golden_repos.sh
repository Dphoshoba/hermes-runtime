#!/usr/bin/env bash
# Clone golden repositories for EVOSIA benchmarking.
# Run from the project root: bash validation/clone_golden_repos.sh

set -euo pipefail

GOLDEN_DIR="validation/golden_repositories"
mkdir -p "$GOLDEN_DIR"

clone_repo() {
    local name="$1"
    local url="$2"
    local dest="$GOLDEN_DIR/$name"
    if [ -d "$dest" ]; then
        echo "  $name already cloned, skipping"
    else
        echo "  Cloning $name..."
        git clone --depth 1 "$url" "$dest" 2>/dev/null
        echo "  Done: $name"
    fi
}

echo "Cloning golden repositories..."

clone_repo "requests" "https://github.com/psf/requests.git"
clone_repo "click" "https://github.com/pallets/click.git"
clone_repo "flask" "https://github.com/pallets/flask.git"
clone_repo "fastapi" "https://github.com/fastapi/fastapi.git"
clone_repo "django" "https://github.com/django/django.git"
clone_repo "numpy" "https://github.com/numpy/numpy.git"
clone_repo "pandas" "https://github.com/pandas-dev/pandas.git"

echo ""
echo "All golden repositories cloned to $GOLDEN_DIR/"
ls -1 "$GOLDEN_DIR/"
