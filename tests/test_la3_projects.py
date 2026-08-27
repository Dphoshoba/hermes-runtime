"""LA3 project authorization tests — path validation, containment, security."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from evosia_agent.path_validation import (
    canonicalize_path,
    is_path_within_authorized_root,
    has_symlink_escape,
    is_sensitive_path,
    compute_local_root_fingerprint,
    validate_project_root,
)
from evosia_agent.project_registry import ProjectRegistry, LocalProject


# ---------------------------------------------------------------------------
# Path Canonicalization Tests
# ---------------------------------------------------------------------------

class TestPathCanonicalization:
    """Verify path canonicalization."""

    def test_canonicalize_absolute_path(self):
        """Canonical path is absolute and normalized."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test"
            path.mkdir()
            canonical = canonicalize_path(path)
            assert canonical.is_absolute()
            assert canonical.exists()

    def test_canonicalize_rejects_nonexistent(self):
        """Non-existent path raises ValueError."""
        with pytest.raises(ValueError):
            canonicalize_path(Path("/nonexistent/path/that/does/not/exist"))


# ---------------------------------------------------------------------------
# Path Containment Tests
# ---------------------------------------------------------------------------

class TestPathContainment:
    """Verify path containment primitive."""

    def test_file_within_root(self):
        """File within root is allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.py").touch()
            assert is_path_within_authorized_root(root / "file.py", root)

    def test_nested_file_within_root(self):
        """Nested file within root is allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subdir = root / "subdir"
            subdir.mkdir()
            (subdir / "file.py").touch()
            assert is_path_within_authorized_root(subdir / "file.py", root)

    def test_traversal_escape_denied(self):
        """../ traversal escape is denied."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            # Attempt to access outside via traversal
            candidate = root / ".." / "outside" / "file.py"
            assert not is_path_within_authorized_root(candidate, root)

    def test_absolute_outside_root_denied(self):
        """Absolute path outside root is denied."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            outside = Path(tmp) / "outside" / "file.py"
            outside.parent.mkdir()
            outside.touch()
            assert not is_path_within_authorized_root(outside, root)


# ---------------------------------------------------------------------------
# Symlink Escape Tests
# ---------------------------------------------------------------------------

class TestSymlinkEscape:
    """Verify symlink escape detection."""

    def test_no_symlinks(self):
        """No symlinks returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.py").touch()
            escaping = has_symlink_escape(root)
            assert len(escaping) == 0

    def test_symlink_within_root(self):
        """Symlink within root is not an escape."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target)
            from evosia_agent.path_validation import SymlinkStatus
            results = has_symlink_escape(root)
            # Safe internal symlinks are still included in results
            assert len(results) == 1
            assert results[0].status == SymlinkStatus.SAFE_INTERNAL

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Windows symlink behavior differs"
    )
    def test_symlink_escape_detected(self):
        """Symlink escaping root is detected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            link = root / "escape"
            link.symlink_to(outside)
            escaping = has_symlink_escape(root)
            assert len(escaping) == 1


# ---------------------------------------------------------------------------
# Sensitive Path Tests
# ---------------------------------------------------------------------------

class TestSensitivePath:
    """Verify sensitive file detection."""

    def test_env_file(self):
        """Env files are sensitive."""
        assert is_sensitive_path(Path(".env"))
        assert is_sensitive_path(Path(".env.local"))
        assert is_sensitive_path(Path(".env.production"))

    def test_key_files(self):
        """Key files are sensitive."""
        assert is_sensitive_path(Path("id_rsa"))
        assert is_sensitive_path(Path("id_ed25519"))
        assert is_sensitive_path(Path("server.pem"))
        assert is_sensitive_path(Path("private.key"))

    def test_git_credentials(self):
        """Git credentials are sensitive."""
        assert is_sensitive_path(Path(".git/credentials"))
        assert is_sensitive_path(Path(".git-credentials"))

    def test_normal_files_not_sensitive(self):
        """Normal code files are not sensitive."""
        assert not is_sensitive_path(Path("main.py"))
        assert not is_sensitive_path(Path("README.md"))
        assert not is_sensitive_path(Path("config.py"))
        assert not is_sensitive_path(Path("settings.py"))
        assert not is_sensitive_path(Path("auth.py"))


# ---------------------------------------------------------------------------
# Fingerprint Tests
# ---------------------------------------------------------------------------

class TestFingerprint:
    """Verify local root fingerprint."""

    def test_fingerprint_deterministic(self):
        """Fingerprint is deterministic."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            fp1 = compute_local_root_fingerprint(path)
            fp2 = compute_local_root_fingerprint(path)
            assert fp1 == fp2

    def test_fingerprint_is_sha256(self):
        """Fingerprint is SHA-256 hex digest."""
        with tempfile.TemporaryDirectory() as tmp:
            fp = compute_local_root_fingerprint(Path(tmp))
            assert len(fp) == 64
            assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# Validate Project Root Tests
# ---------------------------------------------------------------------------

class TestValidateProjectRoot:
    """Verify project root validation."""

    def test_valid_directory(self):
        """Valid directory is accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_project_root(tmp)
            assert result.is_absolute()

    def test_nonexistent_rejected(self):
        """Non-existent path is rejected."""
        with pytest.raises(ValueError, match="does not exist"):
            validate_project_root("/nonexistent/path")

    def test_file_rejected(self):
        """File path is rejected as root."""
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "file.py"
            filepath.touch()
            with pytest.raises(ValueError, match="not a directory"):
                validate_project_root(str(filepath))


# ---------------------------------------------------------------------------
# Project Registry Tests
# ---------------------------------------------------------------------------

class TestProjectRegistry:
    """Verify local project registry."""

    def test_add_and_list(self, tmp_path: Path):
        """Add project and list it."""
        registry = ProjectRegistry(tmp_path)
        proj = registry.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )
        assert proj.display_name == "TestProject"
        assert len(registry.projects) == 1

    def test_get_by_id(self, tmp_path: Path):
        """Get project by ID."""
        registry = ProjectRegistry(tmp_path)
        registry.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )
        proj = registry.get("proj_123")
        assert proj is not None
        assert proj.display_name == "TestProject"

    def test_get_by_path(self, tmp_path: Path):
        """Get project by canonical path."""
        registry = ProjectRegistry(tmp_path)
        registry.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )
        proj = registry.get_by_path("/some/path")
        assert proj is not None

    def test_remove(self, tmp_path: Path):
        """Remove project."""
        registry = ProjectRegistry(tmp_path)
        registry.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )
        assert registry.remove("proj_123")
        assert len(registry.projects) == 0

    def test_revoke(self, tmp_path: Path):
        """Revoke project."""
        registry = ProjectRegistry(tmp_path)
        registry.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )
        assert registry.revoke("proj_123")
        proj = registry.get("proj_123")
        assert proj.status == "revoked"

    def test_persistence(self, tmp_path: Path):
        """Registry persists across instances."""
        registry1 = ProjectRegistry(tmp_path)
        registry1.add(
            cloud_project_id="proj_123",
            canonical_local_root=Path("/some/path"),
            display_name="TestProject",
        )

        registry2 = ProjectRegistry(tmp_path)
        assert len(registry2.projects) == 1
        assert registry2.get("proj_123").display_name == "TestProject"


# ---------------------------------------------------------------------------
# Project Immutability Tests
# ---------------------------------------------------------------------------

class TestProjectImmutability:
    """Verify registration does not modify target project."""

    def test_registration_no_mutation(self):
        """Project tree hash unchanged after registration."""
        import hashlib

        def hash_tree(path: Path) -> str:
            hasher = hashlib.sha256()
            for root, dirs, files in os.walk(path):
                for f in sorted(files):
                    filepath = Path(root) / f
                    hasher.update(str(filepath.relative_to(path)).encode())
                    hasher.update(filepath.read_bytes())
            return hasher.hexdigest()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "file.py").touch()
            (root / "subdir").mkdir()
            (root / "subdir" / "nested.py").touch()

            hash_before = hash_tree(root)

            # Register project
            registry = ProjectRegistry(Path(tmp) / "config")
            registry.add(
                cloud_project_id="proj_test",
                canonical_local_root=root,
                display_name="TestProject",
            )

            hash_after = hash_tree(root)
            assert hash_before == hash_after
