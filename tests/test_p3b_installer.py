"""P3b Installer smoke tests for EVOSIA Connector Windows Installer.

These tests verify the installer configuration is well-formed,
the expected files are packaged, and no secrets are embedded.

NOTE: These tests validate the installer CONFIGURATION, not actual
Windows installation. Windows install/uninstall testing requires
a Windows environment and is documented separately.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
ISS_FILE = REPO_ROOT / "packaging" / "windows" / "evosia_connector.iss"
BUILD_SCRIPT = REPO_ROOT / "packaging" / "windows" / "build_installer.py"
INSTALLER_OUTPUT = REPO_ROOT / "dist" / "connector" / "windows" / "installer"
RUNTIME_ARTIFACT = REPO_ROOT / "dist" / "connector" / "windows" / "evosia-connector-0.1.0-windows-x64-production"


class TestInstallerConfigurationExists:
    """Verify installer configuration files are present."""

    def test_iss_file_exists(self):
        """Inno Setup configuration file exists."""
        assert ISS_FILE.exists(), f"ISS file not found: {ISS_FILE}"

    def test_build_script_exists(self):
        """Installer build script exists."""
        assert BUILD_SCRIPT.exists(), f"Build script not found: {BUILD_SCRIPT}"


class TestInstallerConfiguration:
    """Verify installer configuration is well-formed."""

    def test_iss_file_readable(self):
        """ISS file is readable."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_product_name_correct(self):
        """ISS file contains correct product name."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "EVOSIA Connector" in content

    def test_version_correct(self):
        """ISS file contains correct version."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "0.1.0" in content

    def test_publisher_defined(self):
        """ISS file contains publisher identity."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "Echoes & Visions" in content

    def test_per_user_install(self):
        """Installation scope is per-user (no admin required)."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "PrivilegesRequired=lowest" in content

    def test_no_admin_for_runtime(self):
        """Connector runtime does not require admin elevation."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "PrivilegesRequiredOverridingOwned" in content

    def test_correct_install_location(self):
        """Install location uses localappdata."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "localappdata" in content
        assert "Programs" in content

    def test_start_menu_shortcut(self):
        """Start Menu shortcut is configured."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "[Icons]" in content
        assert "{group}" in content

    def test_uninstall_configured(self):
        """Uninstall is properly configured."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "UninstallDisplayName" in content
        assert "UninstallDisplayIcon" in content

    def test_x64_targeted(self):
        """Architecture targets x64."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "x64compatible" in content

    def test_running_process_handled(self):
        """Installer handles running EVOSIA Connector process."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "evosia-connector.exe" in content
        assert "taskkill" in content

    def test_lzma_compression(self):
        """Installer uses solid compression."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "SolidCompression=yes" in content

    def test_no_desktop_shortcut_default(self):
        """Desktop shortcut is NOT created by default."""
        content = ISS_FILE.read_text(encoding="utf-8")
        # No desktop shortcut entry in [Icons]
        lines = [l for l in content.split("\n") if "{autodesktop}" in l.lower() or "desktop" in l.lower()]
        # Should not have any desktop shortcut entries in Icons section
        icons_section = content.split("[Icons]")[1] if "[Icons]" in content else ""
        assert "{autodesktop}" not in icons_section.lower()


class TestInstallerFileContents:
    """Verify expected files are packaged in the installer input."""

    def test_runtime_artifact_exists(self):
        """P3a runtime artifact directory exists."""
        if RUNTIME_ARTIFACT.exists():
            assert RUNTIME_ARTIFACT.is_dir()
        else:
            pytest.skip("P3a runtime not built yet")

    def test_runtime_has_executable(self):
        """Runtime artifact contains the entry point."""
        if not RUNTIME_ARTIFACT.exists():
            pytest.skip("P3a runtime not built yet")
        # On macOS, .exe won't exist but the binary should
        exe_path = RUNTIME_ARTIFACT / "evosia-connector.exe"
        unix_path = RUNTIME_ARTIFACT / "evosia-connector"
        assert exe_path.exists() or unix_path.exists(), (
            f"No executable found in {RUNTIME_ARTIFACT}"
        )

    def test_no_test_files_in_runtime(self):
        """Runtime artifact does not contain test files."""
        if not RUNTIME_ARTIFACT.exists():
            pytest.skip("P3a runtime not built yet")
        test_files = list(RUNTIME_ARTIFACT.rglob("test_*.py"))
        assert len(test_files) == 0, f"Test files found in runtime: {test_files}"

    def test_no_source_tree_in_runtime(self):
        """Runtime artifact does not contain repository source tree."""
        if not RUNTIME_ARTIFACT.exists():
            pytest.skip("P3a runtime not built yet")
        # Check no git directory
        git_dirs = list(RUNTIME_ARTIFACT.rglob(".git"))
        assert len(git_dirs) == 0, f"Git directory found in runtime: {git_dirs}"

    def test_no_dev_files_in_runtime(self):
        """Runtime artifact does not contain development files."""
        if not RUNTIME_ARTIFACT.exists():
            pytest.skip("P3a runtime not built yet")
        dev_files = [
            ".env",
            ".env.example",
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
        ]
        for f in dev_files:
            path = RUNTIME_ARTIFACT / f
            assert not path.exists(), f"Dev file found in runtime: {f}"


class TestInstallerSecretsCheck:
    """Verify no secrets are embedded in installer configuration."""

    def test_no_embedded_tokens(self):
        """ISS file does not contain tokens."""
        content = ISS_FILE.read_text(encoding="utf-8").lower()
        secret_patterns = ["bearer ", "authorization:", "api_key", "secret_key", "token="]
        for pattern in secret_patterns:
            assert pattern not in content, f"Secret pattern found in ISS: {pattern}"

    def test_no_api_keys(self):
        """ISS file does not contain API keys."""
        content = ISS_FILE.read_text(encoding="utf-8")
        assert "sk-" not in content
        assert "pk-" not in content


class TestInstallerBuildScript:
    """Verify installer build script is well-formed."""

    def test_script_executable(self):
        """Build script is a valid Python file."""
        content = BUILD_SCRIPT.read_text(encoding="utf-8")
        assert "def main" in content

    def test_script_has_version(self):
        """Build script uses connector version."""
        content = BUILD_SCRIPT.read_text(encoding="utf-8")
        assert "CONNECTOR_PRODUCT_VERSION" in content

    def test_script_checks_runtime(self):
        """Build script verifies P3a runtime exists."""
        content = BUILD_SCRIPT.read_text(encoding="utf-8")
        assert "RUNTIME_ARTIFACT" in content


class TestInstallerOutput:
    """Verify installer artifact (if built)."""

    def test_installer_directory_exists(self):
        """Installer output directory exists (if built)."""
        if INSTALLER_OUTPUT.exists():
            assert INSTALLER_OUTPUT.is_dir()
        else:
            pytest.skip("Installer not built yet")

    def test_installer_has_exe(self):
        """Installer output contains setup .exe."""
        if not INSTALLER_OUTPUT.exists():
            pytest.skip("Installer not built yet")
        exe_files = list(INSTALLER_OUTPUT.glob("*.exe"))
        assert len(exe_files) > 0, "No .exe found in installer output"

    def test_installer_name_format(self):
        """Installer filename follows naming convention."""
        if not INSTALLER_OUTPUT.exists():
            pytest.skip("Installer not built yet")
        exe_files = list(INSTALLER_OUTPUT.glob("*.exe"))
        for f in exe_files:
            name = f.name
            assert "EVOSIA" in name or "evosia" in name.lower()
            assert "0.1.0" in name
            assert "windows" in name.lower()
