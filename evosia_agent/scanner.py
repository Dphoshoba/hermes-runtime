"""Scanner — bounded read-only project inspection for LA4.

Implements deterministic, read-only scanning of authorized project roots.
Never modifies files, never executes project code, never runs shell commands.
"""

from __future__ import annotations

import os
import subprocess
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
    languages: list[str] = field(default_factory=list)
    project_structure_summary: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    truncated: bool = False
    limits: dict = field(default_factory=dict)
    sensitive_files_found: list[str] = field(default_factory=list)
    total_bytes_read: int = 0
    git_metadata: dict | None = None


# ---------------------------------------------------------------------------
# Git Metadata Adapter (Narrow, Allowlisted)
# ---------------------------------------------------------------------------

_GIT_ALLOWLIST = frozenset({
    "rev-parse --abbrev-ref HEAD",
    "rev-parse HEAD",
    "status --porcelain",
})


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
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
                env={k: v for k, v in os.environ.items() if k not in (
                    "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_NAME",
                    "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_NAME",
                )},
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

    # Canonicalize the root
    try:
        root_resolved = canonicalize_path(project_root)
    except ValueError:
        return result

    # Detect languages and collect structure
    languages: set[str] = set()
    file_count = 0
    total_bytes = 0
    directory_count = 0
    structure: dict = {}

    # Track visited paths to prevent symlink cycles
    visited: set[tuple[Path, Path]] = set()

    try:
        for item in project_root.rglob("*"):
            # Check resource limits
            if file_count >= limits.max_file_count:
                result.truncated = True
                break
            if total_bytes >= limits.max_total_bytes:
                result.truncated = True
                break

            # Prevent symlink cycles
            try:
                item_resolved = item.resolve()
            except (OSError, ValueError):
                continue
            cycle_id = (item_resolved, item)
            if cycle_id in visited:
                continue
            visited.add(cycle_id)

            # Handle symlinks
            if item.is_symlink():
                symlink_result = check_symlink(item, root_resolved)
                if symlink_result.status == SymlinkStatus.ESCAPES_ROOT:
                    result.findings.append({
                        "type": "SYMLINK_ESCAPE",
                        "path": str(item.relative_to(project_root)),
                        "classification": "ESCAPING_SYMLINK",
                    })
                    continue
                elif symlink_result.status == SymlinkStatus.BROKEN_OR_UNRESOLVABLE:
                    result.findings.append({
                        "type": "BROKEN_SYMLINK",
                        "path": str(item.relative_to(project_root)),
                        "classification": "BROKEN_SYMLINK",
                    })
                    continue

            if item.is_dir():
                directory_count += 1
                dir_name = item.name
                structure[dir_name] = structure.get(dir_name, 0) + 1
                continue

            if not item.is_file():
                continue

            file_count += 1
            rel_path = item.relative_to(project_root)

            # Check sensitive files
            if is_sensitive_path(item):
                result.sensitive_files_found.append(str(rel_path))
                result.findings.append({
                    "type": "SENSITIVE_FILE",
                    "path": str(rel_path),
                    "classification": "SENSITIVE_FILE",
                    "content_read": False,
                })
                continue

            # Check file extension
            ext = item.suffix.lower()
            if ext in BINARY_EXTENSIONS:
                result.findings.append({
                    "type": "BINARY_FILE",
                    "path": str(rel_path),
                    "classification": "BINARY_FILE",
                })
                continue

            if ext not in PERMITTED_EXTENSIONS:
                continue

            # Detect language
            lang = EXTENSION_LANGUAGE_MAP.get(ext)
            if lang:
                languages.add(lang)

            # Check file size
            try:
                file_size = item.stat().st_size
            except OSError:
                continue

            if file_size > limits.max_file_size:
                result.findings.append({
                    "type": "OVERSIZED_FILE",
                    "path": str(rel_path),
                    "classification": "OVERSIZED_FILE",
                    "size_bytes": file_size,
                })
                continue

            # Check aggregate bytes
            if total_bytes + file_size > limits.max_total_bytes:
                result.truncated = True
                break

            # Read file content (safe text read only)
            try:
                content = item.read_text(encoding="utf-8", errors="replace")
                total_bytes += len(content.encode("utf-8"))
            except (OSError, UnicodeDecodeError):
                continue

    except (OSError, ValueError):
        # Permission errors or other issues — return what we found
        pass

    # Get git metadata (narrow, safe)
    result.git_metadata = _get_git_metadata(project_root)

    # Compile results
    result.file_count = file_count
    result.languages = sorted(languages)
    result.total_bytes_read = total_bytes
    result.project_structure_summary = {
        "directory_count": directory_count,
        "file_count": file_count,
        "languages": result.languages,
    }

    return result
