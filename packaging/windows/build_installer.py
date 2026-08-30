#!/usr/bin/env python3
"""Build script for EVOSIA Connector Windows Installer — P3b.

Builds the Windows installer using Inno Setup, consuming the P3a
PyInstaller directory bundle as input.

Usage:
    python packaging/windows/build_installer.py

Prerequisites:
    - Inno Setup 6+ installed (iscc.exe in PATH or ISCC_PATH configured)
    - P3a runtime bundle built at dist/connector/windows/evosia-connector-*-windows-x64-production/

Output:
    dist/connector/windows/installer/EVOSIA-Connector-*-windows-x64-production-setup.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent

# Version info
sys.path.insert(0, str(ROOT))
from evosia_connector.version import CONNECTOR_PRODUCT_VERSION, BUILD_CHANNEL

# Build paths
DIST_BASE = ROOT / "dist" / "connector" / "windows"
RUNTIME_ARTIFACT = DIST_BASE / f"evosia-connector-{CONNECTOR_PRODUCT_VERSION}-windows-x64-{BUILD_CHANNEL}"
INSTALLER_OUTPUT = DIST_BASE / "installer"
ISS_FILE = Path(__file__).resolve().parent / "evosia_connector.iss"

# Inno Setup compiler path — check common locations
ISCC_PATHS = [
    shutil.which("iscc"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def find_iscc() -> str | None:
    """Find Inno Setup compiler."""
    for path in ISCC_PATHS:
        if path and os.path.isfile(path):
            return path
    return None


def clean_prior_installer() -> None:
    """Remove prior installer outputs."""
    if INSTALLER_OUTPUT.exists():
        print(f"Cleaning {INSTALLER_OUTPUT}...")
        shutil.rmtree(INSTALLER_OUTPUT)
    INSTALLER_OUTPUT.mkdir(parents=True, exist_ok=True)


def verify_runtime_artifact() -> None:
    """Verify P3a runtime bundle exists and is valid."""
    if not RUNTIME_ARTIFACT.exists():
        sys.exit(
            f"P3a runtime artifact not found: {RUNTIME_ARTIFACT}\n"
            f"Build the P3a runtime first: python packaging/build_connector.py"
        )

    exe_path = RUNTIME_ARTIFACT / "evosia-connector.exe"
    # On non-Windows, the .exe won't exist but the directory should
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Runtime executable: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"Runtime directory: {RUNTIME_ARTIFACT}")
        contents = list(RUNTIME_ARTIFACT.iterdir())
        print(f"  Contains {len(contents)} entries")


def build_installer(iscc_path: str) -> None:
    """Run Inno Setup compiler."""
    print(f"Building installer with Inno Setup...")
    print(f"  ISS file: {ISS_FILE}")
    print(f"  Output:   {INSTALLER_OUTPUT}")

    result = subprocess.run(
        [
            iscc_path,
            f"/O{INSTALLER_OUTPUT}",
            str(ISS_FILE),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    print("STDOUT:", result.stdout)

    if result.returncode != 0:
        print("STDERR:", result.stderr)
        sys.exit(f"Inno Setup failed with exit code {result.returncode}")

    print("Installer built successfully.")


def verify_installer() -> None:
    """Verify installer artifact exists."""
    expected_name = f"EVOSIA-Connector-{CONNECTOR_PRODUCT_VERSION}-windows-x64-{BUILD_CHANNEL}-setup.exe"
    installer_path = INSTALLER_OUTPUT / expected_name

    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"Installer: {installer_path}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        # Check what files exist in installer output
        if INSTALLER_OUTPUT.exists():
            files = list(INSTALLER_OUTPUT.glob("*.exe"))
            if files:
                for f in files:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    print(f"Installer: {f}")
                    print(f"Size: {size_mb:.1f} MB")
            else:
                print(f"Warning: No .exe found in {INSTALLER_OUTPUT}")
        else:
            sys.exit(f"Installer output directory not found: {INSTALLER_OUTPUT}")


def main() -> None:
    """Main build process."""
    print("=== EVOSIA Connector Windows Installer Build ===")
    print(f"Version: {CONNECTOR_PRODUCT_VERSION}")
    print(f"Channel: {BUILD_CHANNEL}")
    print()

    # Find Inno Setup
    iscc_path = find_iscc()
    if not iscc_path:
        sys.exit(
            "Inno Setup compiler (iscc.exe) not found.\n"
            "Install Inno Setup 6+ from https://jrsoftware.org/isinfo.php\n"
            "or set ISCC_PATH environment variable."
        )
    print(f"Inno Setup: {iscc_path}")

    clean_prior_installer()
    verify_runtime_artifact()
    build_installer(iscc_path)
    verify_installer()

    print()
    print("=== Installer Build Complete ===")


if __name__ == "__main__":
    main()
