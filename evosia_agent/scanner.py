"""Scanner — bounded read-only project inspection for LA4.

Implements deterministic, read-only scanning of authorized project roots.
Never modifies files, never executes project code, never runs shell commands.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .path_validation import (
    SymlinkStatus,
    canonicalize_path,
    check_symlink,
    is_sensitive_path,
    is_path_within_authorized_root,
)


# ---------------------------------------------------------------------------
# Resource Limits
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 1_048_576  # 1 MB per file
MAX_TOTAL_BYTES_READ = 10_485_760  # 10 MB aggregate
MAX_FILE_COUNT = 5_000
SCAN_TIMEOUT_SECONDS = 120
EXCLUDED_DIRECTORY_NAMES = frozenset({
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "dist",
    "build",
    "coverage",
    ".coverage",
    "htmlcov",
})

# Permitted text/source file extensions
PERMITTED_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".cs", ".swift", ".m",
    ".html", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".xml", ".svg", ".md", ".rst", ".txt",
    ".sql", ".sh", ".bash", ".zsh",
    ".env", ".env.local", ".env.production", ".env.development",
    ".gitignore", ".gitattributes",
    ".dockerignore", "Dockerfile",
    "Makefile", "CMakeLists.txt",
    ".lock", ".sum",
})

# Binary file extensions — exclude from content reading
BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pyc", ".pyo", ".class", ".jar",
    ".woff", ".woff2", ".ttf", ".eot",
})

# Language detection mapping
EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".sql": "SQL",
    ".sh": "Shell",
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ScanLimits:
    """Resource limits for a scan operation."""
    max_file_size: int = MAX_FILE_SIZE_BYTES
    max_total_bytes: int = MAX_TOTAL_BYTES_READ
    max_file_count: int = MAX_FILE_COUNT
    timeout_seconds: int = SCAN_TIMEOUT_SECONDS


@dataclass
class ScanResult:
    """Result of a bounded read-only project scan."""
    file_count: int = 0
    files_discovered: int = 0
    files_examined: int = 0
    files_skipped: int = 0
    files_excluded_by_policy: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    exclusion_reasons: dict[str, int] = field(default_factory=dict)
    excluded_directories: dict[str, int] = field(default_factory=dict)
    limits_reached: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    project_structure_summary: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    truncated: bool = False
    limits: dict = field(default_factory=dict)
    sensitive_files_found: list[str] = field(default_factory=list)
    total_bytes_read: int = 0
    bytes_examined: int = 0
    git_metadata: dict | None = None


# ---------------------------------------------------------------------------
# Git Metadata Adapter (Narrow, Allowlisted)
# ---------------------------------------------------------------------------

_GIT_ALLOWLIST = frozenset({
    "rev-parse --abbrev-ref HEAD",
    "rev-parse HEAD",
    "status --porcelain",
})


def is_policy_excluded_directory(path: str | Path) -> bool:
    """Return whether any normalized path component is excluded by policy."""
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    return any(part.lower() in EXCLUDED_DIRECTORY_NAMES for part in parts)


def _count_files_below(directory: Path) -> int:
    """Count file entries under a pruned directory without following symlinks."""
    count = 0

    def raise_walk_error(error: OSError) -> None:
        raise error

    for _, _, filenames in os.walk(
        directory,
        topdown=True,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        count += len(filenames)
    return count


def _git_ignored_paths(project_root: Path, relative_paths: list[str]) -> set[str]:
    """Ask Git to apply repository ignore rules to a batch of paths."""
    if not relative_paths or not (project_root / ".git").exists():
        return set()

    try:
        completed = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=str(project_root),
            input=b"".join(os.fsencode(path) + b"\0" for path in relative_paths),
            capture_output=True,
            timeout=5,
            check=False,
            shell=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()

    if completed.returncode not in (0, 1):
        raise OSError("Repository ignore rules could not be evaluated")
    return {
        os.fsdecode(path)
        for path in completed.stdout.split(b"\0")
        if path
    }


def _get_git_metadata(project_root: Path) -> dict | None:
    """Safely extract git metadata using a narrow allowlist.

    Returns None if not a git repo or if git is unavailable.
    Never runs arbitrary commands.
    """
    git_dir = project_root / ".git"
    if not git_dir.exists():
        return None

    metadata = {}
    for cmd_str in _GIT_ALLOWLIST:
        cmd = ["git"] + cmd_str.split()
        try:
            git_env = os.environ.copy()
            git_env["GIT_OPTIONAL_LOCKS"] = "0"
            for variable in (
                "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_NAME",
                "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_NAME",
            ):
                git_env.pop(variable, None)
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
                env=git_env,
            )
            if result.returncode == 0:
                key = cmd_str.replace(" ", "_").replace("-", "")
                metadata[key] = result.stdout.strip()[:500]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    return metadata if metadata else None


# ---------------------------------------------------------------------------
# Core Scanner
# ---------------------------------------------------------------------------

def scan_project(
    project_root: Path,
    limits: ScanLimits | None = None,
) -> ScanResult:
    """Perform a bounded, read-only scan of an authorized project.

    This is the ONLY scanning entry point for LA4.
    Never modifies files, never executes project code.

    Returns a ScanResult with safe metadata only.
    """
    if limits is None:
        limits = ScanLimits()

    result = ScanResult(
        limits={
            "max_file_size": limits.max_file_size,
            "max_total_bytes": limits.max_total_bytes,
            "max_file_count": limits.max_file_count,
            "timeout_seconds": limits.timeout_seconds,
        }
    )
    scan_started = time.monotonic()

    def record_skip(reason: str) -> None:
        result.files_skipped += 1
        result.skip_reasons[reason] = result.skip_reasons.get(reason, 0) + 1

    def record_exclusion(reason: str, file_count: int) -> None:
        result.files_excluded_by_policy += file_count
        result.exclusion_reasons[reason] = (
            result.exclusion_reasons.get(reason, 0) + file_count
        )

    def record_limit(name: str) -> None:
        result.truncated = True
        if name not in result.limits_reached:
            result.limits_reached.append(name)

    # Canonicalize the root
    try:
        root_resolved = canonicalize_path(project_root)
    except ValueError:
        raise OSError("The authorized project root could not be resolved")
    if not root_resolved.is_dir():
        raise OSError("The authorized project root is not an accessible directory")

    # Detect languages and collect structure
    languages: set[str] = set()
    file_count = 0
    total_bytes = 0
    directory_count = 0
    structure: dict = {}

    # Track visited paths to prevent symlink cycles
    visited: set[tuple[Path, Path]] = set()

    def raise_walk_error(error: OSError) -> None:
        raise error

    def add_finding(
        finding_type: str,
        path: Path,
        title: str,
        category: str,
        description: str,
        **metadata: object,
    ) -> None:
        module = path.relative_to(root_resolved).as_posix()
        result.findings.append({
            "type": finding_type,
            "path": module,
            "module": module,
            "title": title,
            "category": category,
            "description": description,
            **metadata,
        })

    try:
        for current_root, dirnames, filenames in os.walk(
            root_resolved,
            topdown=True,
            followlinks=False,
            onerror=raise_walk_error,
        ):
            current_path = Path(current_root)
            for name in (*dirnames, *filenames):
                item = current_path / name
                is_file_entry = name in filenames
                # Handle symlinks
                if item.is_symlink():
                    symlink_result = check_symlink(item, root_resolved)
                    if symlink_result.status == SymlinkStatus.ESCAPES_ROOT:
                        if is_file_entry:
                            file_count += 1
                            result.files_discovered += 1
                            record_skip("symlink_escape")
                        add_finding(
                            "SYMLINK_ESCAPE",
                            item,
                            f"Symlink escapes project: {item.name}",
                            "Project boundary",
                            "This symlink resolves outside the authorized project "
                            "root and must not be followed.",
                            classification="ESCAPING_SYMLINK",
                        )
                        if is_file_entry:
                            filenames.remove(name)
                        else:
                            dirnames.remove(name)
                        continue
                    elif symlink_result.status == SymlinkStatus.BROKEN_OR_UNRESOLVABLE:
                        if is_file_entry:
                            file_count += 1
                            result.files_discovered += 1
                            record_skip("broken_symlink")
                        add_finding(
                            "BROKEN_SYMLINK",
                            item,
                            f"Broken project symlink: {item.name}",
                            "Project integrity",
                            "This symlink target cannot be resolved and should be "
                            "repaired or removed.",
                            classification="BROKEN_SYMLINK",
                        )
                        if is_file_entry:
                            filenames.remove(name)
                        else:
                            dirnames.remove(name)
                        continue
                    elif not is_file_entry:
                        dirnames.remove(name)
                        continue

                try:
                    item_resolved = item.resolve()
                except (OSError, ValueError) as exc:
                    raise OSError("A project entry could not be resolved") from exc
                cycle_id = (item_resolved, item)
                if cycle_id in visited:
                    continue
                visited.add(cycle_id)

            excluded_dirs = [
                name for name in dirnames
                if is_policy_excluded_directory(name)
            ]
            for name in excluded_dirs:
                excluded_count = _count_files_below(current_path / name)
                record_exclusion(f"excluded_directory:{name.lower()}", excluded_count)
                result.excluded_directories[name.lower()] = (
                    result.excluded_directories.get(name.lower(), 0) + 1
                )
                dirnames.remove(name)

            policy_excluded_files = [
                name for name in filenames
                if is_policy_excluded_directory(name)
            ]
            for name in policy_excluded_files:
                record_exclusion(f"excluded_file:{name.lower()}", 1)
                filenames.remove(name)

            candidate_names = [*dirnames, *filenames]
            candidate_paths = {
                name: (current_path / name).relative_to(root_resolved).as_posix()
                for name in candidate_names
            }
            ignored_paths = _git_ignored_paths(
                root_resolved,
                list(candidate_paths.values()),
            )
            ignored_directories = set()
            for name in dirnames:
                if candidate_paths[name] not in ignored_paths:
                    continue
                ignored_directories.add(name)
                result.excluded_directories["gitignore"] = (
                    result.excluded_directories.get("gitignore", 0) + 1
                )
            for name in list(filenames):
                item = current_path / name
                if (
                    candidate_paths[name] in ignored_paths
                    and not is_sensitive_path(item)
                ):
                    record_exclusion("gitignore", 1)
                    filenames.remove(name)

            for name in dirnames:
                if name in ignored_directories:
                    continue
                directory_count += 1
                structure[name] = structure.get(name, 0) + 1

            for name in filenames:
                item = current_path / name
                if not item.is_file():
                    continue

                file_count += 1
                result.files_discovered += 1
                rel_path = item.relative_to(root_resolved)

                if file_count > limits.max_file_count:
                    record_limit("max_file_count")
                    record_skip("max_file_count")
                    continue

                if time.monotonic() - scan_started >= limits.timeout_seconds:
                    record_limit("timeout_seconds")
                    record_skip("timeout_seconds")
                    continue

                # Check sensitive files
                if is_sensitive_path(item):
                    module = rel_path.as_posix()
                    result.sensitive_files_found.append(module)
                    add_finding(
                        "SENSITIVE_FILE",
                        item,
                        f"Sensitive file present: {item.name}",
                        "Sensitive data exposure",
                        "This file name indicates potentially sensitive material. "
                        "Its contents were not read; verify it is not committed or "
                        "otherwise exposed.",
                        classification="SENSITIVE_FILE",
                        content_read=False,
                    )
                    record_skip("sensitive_file")
                    continue

                # Check file extension
                ext = item.suffix.lower()
                if ext in BINARY_EXTENSIONS:
                    record_skip("binary_file")
                    continue

                if ext not in PERMITTED_EXTENSIONS:
                    record_skip("unsupported_file_type")
                    continue

                # Detect language
                lang = EXTENSION_LANGUAGE_MAP.get(ext)
                if lang:
                    languages.add(lang)

                # Check file size
                try:
                    file_size = item.stat().st_size
                except OSError:
                    record_skip("unreadable_metadata")
                    continue

                if file_size > limits.max_file_size:
                    record_limit("max_file_size")
                    record_skip("max_file_size")
                    continue

                # Check aggregate bytes
                if total_bytes + file_size > limits.max_total_bytes:
                    record_limit("max_total_bytes")
                    record_skip("max_total_bytes")
                    continue

                # Read file content (safe text read only)
                try:
                    item.read_text(encoding="utf-8", errors="replace")
                    total_bytes += file_size
                    result.files_examined += 1
                except (OSError, UnicodeDecodeError):
                    record_skip("unreadable_file")
                    continue

    except (OSError, ValueError) as exc:
        raise OSError("The authorized project could not be fully enumerated") from exc

    # Get git metadata (narrow, safe)
    result.git_metadata = _get_git_metadata(project_root)

    # Compile results
    result.file_count = file_count
    result.languages = sorted(languages)
    result.total_bytes_read = total_bytes
    result.bytes_examined = total_bytes
    result.project_structure_summary = {
        "directory_count": directory_count,
        "file_count": file_count,
        "languages": result.languages,
    }

    return result
