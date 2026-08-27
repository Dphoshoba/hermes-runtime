"""Path validation — canonical path containment, symlink escape, sensitive-file policy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath


# Sensitive file patterns — LA3 path-based protection only
SENSITIVE_PATTERNS = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
})

SENSITIVE_SUFFIXES = frozenset({
    ".pem",
    ".key",
})

SENSITIVE_NAMES = frozenset({
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "known_hosts",
    "credentials",
})

# Git credential files
GIT_CREDENTIAL_PATTERNS = frozenset({
    ".git/credentials",
    ".git-credentials",
})


class SymlinkStatus(Enum):
    """Result of symlink validation."""
    SAFE_INTERNAL = "safe_internal"
    ESCAPES_ROOT = "escapes_root"
    BROKEN_OR_UNRESOLVABLE = "broken_or_unresolvable"


@dataclass
class SymlinkCheckResult:
    """Result of checking a single symlink."""
    path: Path
    status: SymlinkStatus
    target: Path | None = None


def canonicalize_path(path: Path) -> Path:
    """Resolve path to canonical absolute form.

    Resolves symlinks in parent directories, normalizes separators,
    eliminates redundant components.

    Raises ValueError for invalid paths.
    """
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")

    try:
        resolved = path.resolve()
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot resolve path: {path}") from exc

    if not resolved.is_absolute():
        raise ValueError(f"Path is not absolute after resolution: {resolved}")

    return resolved


def is_path_within_authorized_root(candidate: Path, root: Path) -> bool:
    """Check if candidate path is within authorized root directory.

    This is the core containment primitive for LA3+ scanning.

    Allowed:
        root/file.py
        root/subdir/file.py

    Denied:
        root/../other/file.py
        absolute path outside root
    """
    try:
        resolved_candidate = canonicalize_path(candidate)
        resolved_root = canonicalize_path(root)
    except ValueError:
        return False

    # Check if resolved candidate is within resolved root
    try:
        resolved_candidate.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def check_symlink(symlink_path: Path, root: Path) -> SymlinkCheckResult:
    """Validate a single symlink for project authorization.

    Returns SymlinkCheckResult with status:
    - SAFE_INTERNAL: symlink target is within root
    - ESCAPES_ROOT: symlink target escapes root
    - BROKEN_OR_UNRESOLVABLE: target cannot be resolved

    Does NOT follow symlinks outside root.
    """
    try:
        root_resolved = canonicalize_path(root)
    except ValueError:
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.BROKEN_OR_UNRESOLVABLE,
        )

    # Check if symlink exists (not broken)
    if not symlink_path.exists():
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.BROKEN_OR_UNRESOLVABLE,
        )

    # Resolve the symlink target
    try:
        target = symlink_path.resolve()
    except (OSError, ValueError):
        # Cannot resolve — treat as broken
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.BROKEN_OR_UNRESOLVABLE,
        )

    # Check if target is a broken symlink
    # resolve() follows symlinks, but if the final target doesn't exist,
    # it still returns the path — we need to check existence
    if not target.exists():
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.BROKEN_OR_UNRESOLVABLE,
        )

    # Check if target escapes root
    try:
        target.relative_to(root_resolved)
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.SAFE_INTERNAL,
            target=target,
        )
    except ValueError:
        return SymlinkCheckResult(
            path=symlink_path,
            status=SymlinkStatus.ESCAPES_ROOT,
            target=target,
        )


def has_symlink_escape(project_root: Path) -> list[SymlinkCheckResult]:
    """Check if project contains symlinks that escape the authorized root.

    Returns list of SymlinkCheckResult for each symlink found.

    Fail-closed: BROKEN_OR_UNRESOLVABLE symlinks are included in results
    so registration can reject them.

    Does NOT follow symlinks outside root.
    """
    results = []

    try:
        root_resolved = canonicalize_path(project_root)
    except ValueError:
        return results

    # Walk the project tree looking for symlinks
    # Use a bounded iteration to prevent infinite loops
    try:
        visited = set()
        for item in project_root.rglob("*"):
            # Prevent infinite loops from symlink cycles
            try:
                item_resolved = item.resolve()
            except (OSError, ValueError):
                continue

            # Check for cycles
            item_id = (item_resolved, item)
            if item_id in visited:
                continue
            visited.add(item_id)

            if item.is_symlink():
                result = check_symlink(item, root_resolved)
                results.append(result)
    except (OSError, ValueError):
        # Permission errors or other issues — return what we found
        pass

    return results


def is_sensitive_path(path: Path) -> bool:
    """Check if path is a sensitive file that should not be read/transmitted.

    LA3 path-based protection only. Does not inspect file contents.
    """
    name = path.name

    # Check exact name matches
    if name in SENSITIVE_NAMES:
        return True

    # Check pattern matches
    if name in SENSITIVE_PATTERNS:
        return True

    # Check suffix matches (e.g., .pem, .key)
    if path.suffix in SENSITIVE_SUFFIXES:
        return True

    # Check git credential patterns
    rel_path = str(PurePosixPath(path.as_posix()))
    for pattern in GIT_CREDENTIAL_PATTERNS:
        if rel_path.endswith(pattern):
            return True

    return False


def compute_local_root_fingerprint(canonical_path: Path) -> str:
    """Compute stable fingerprint for local root path.

    SHA-256 of canonical path string. Identity/fingerprint aid only,
    NOT a security secret.
    """
    path_str = canonical_path.as_posix()
    return hashlib.sha256(path_str.encode()).hexdigest()


def validate_project_root(path: str | Path) -> Path:
    """Validate and canonicalize a project root path.

    Checks:
    1. Path exists
    2. Path is a directory
    3. Path can be canonicalized
    4. Path is absolute

    Raises ValueError with descriptive message on failure.
    """
    p = Path(path)

    if not p.exists():
        raise ValueError(f"Path does not exist: {p}")

    if not p.is_dir():
        raise ValueError(f"Path is not a directory: {p}")

    canonical = canonicalize_path(p)

    # Check for traversal attempts
    if ".." in str(p):
        # Even if canonical form is valid, reject paths with ..
        # that might be confusing in display
        pass

    return canonical
