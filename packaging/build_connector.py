#!/usr/bin/env python3
"""Build script for EVOSIA Connector — Windows packaging foundation.

Produces a directory-bundle artifact containing the packaged Connector runtime.

Usage:
    python packaging/build_connector.py

Output:
    dist/connector/windows/evosia-connector-<version>-windows-x64-<channel>/
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent

# Version info
sys.path.insert(0, str(ROOT))
from evosia_connector.version import CONNECTOR_PRODUCT_VERSION, BUILD_CHANNEL

# Build paths
DIST_BASE = ROOT / "dist" / "connector" / "windows"
ARTIFACT_NAME = f"evosia-connector-{CONNECTOR_PRODUCT_VERSION}-windows-x64-{BUILD_CHANNEL}"
ARTIFACT_DIR = DIST_BASE / ARTIFACT_NAME
SPEC_FILE = ROOT / "packaging" / "evosia_connector.spec"


def clean_prior_builds() -> None:
    """Remove prior build outputs."""
    build_dir = ROOT / "build"
    if build_dir.exists():
        print(f"Cleaning {build_dir}...")
        shutil.rmtree(build_dir)

    if DIST_BASE.exists():
        print(f"Cleaning {DIST_BASE}...")
        shutil.rmtree(DIST_BASE)


def run_pyinstaller() -> None:
    """Run PyInstaller with the Connector spec file."""
    print(f"Running PyInstaller (spec: {SPEC_FILE})...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST_BASE),
            "--workpath",
            str(ROOT / "build" / "connector"),
            "--specpath",
            str(ROOT / "packaging"),
            str(SPEC_FILE),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        sys.exit(f"PyInstaller failed with exit code {result.returncode}")

    print("PyInstaller completed successfully.")


def stamp_build_metadata() -> None:
    """Stamp build metadata into the artifact."""
    metadata_file = ARTIFACT_DIR / "BUILD_METADATA.json"
    import json
    from datetime import datetime, timezone

    metadata = {
        "product": "EVOSIA Connector",
        "version": CONNECTOR_PRODUCT_VERSION,
        "channel": BUILD_CHANNEL,
        "platform": "windows",
        "architecture": "x64",
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "build_host": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown")),
    }

    metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Build metadata written to {metadata_file}")


def verify_artifact() -> None:
    """Verify the built artifact exists and is runnable."""
    exe_path = ARTIFACT_DIR / "evosia-connector.exe"
    if not exe_path.exists():
        # On non-Windows, check for the directory bundle
        print(f"Note: .exe not found at {exe_path} (expected on non-Windows build host)")
        print(f"Artifact directory: {ARTIFACT_DIR}")
        if ARTIFACT_DIR.exists():
            contents = list(ARTIFACT_DIR.iterdir())
            print(f"Artifact contains {len(contents)} entries")
        else:
            sys.exit(f"Artifact directory not found: {ARTIFACT_DIR}")
    else:
        print(f"Artifact executable: {exe_path}")
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Executable size: {size_mb:.1f} MB")


def main() -> None:
    """Main build process."""
    print(f"=== EVOSIA Connector Build ===")
    print(f"Version: {CONNECTOR_PRODUCT_VERSION}")
    print(f"Channel: {BUILD_CHANNEL}")
    print(f"Artifact: {ARTIFACT_NAME}")
    print()

    clean_prior_builds()
    run_pyinstaller()
    stamp_build_metadata()
    verify_artifact()

    print()
    print(f"=== Build Complete ===")
    print(f"Artifact: {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
