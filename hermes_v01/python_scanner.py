"""Repository Intelligence — Python Scanner.

Adapts the existing Python scanner to the multi-language scanner interface.
Preserves all existing Python analysis behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scanner_registry import RepositoryScanner


class PythonScanner(RepositoryScanner):
    """Python repository scanner using existing repo_scanner module."""

    @property
    def scanner_id(self) -> str:
        return "python"

    @property
    def supported_languages(self) -> tuple[str, ...]:
        return ("python",)

    def detect(self, repo_root: Path) -> dict[str, Any]:
        """Detect Python files in the repository."""
        evidence: list[str] = []
        file_count = 0

        # Check for Python manifest files
        for manifest in ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"]:
            if (repo_root / manifest).exists():
                evidence.append(f"Found {manifest}")

        # Count Python files
        for dirpath, dirnames, filenames in repo_root.walk():
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in ("__pycache__", "node_modules", ".git", "build", "dist", "venv", ".venv", "validation")
            ]
            for fname in filenames:
                if fname.endswith(".py"):
                    file_count += 1

        confidence = min(1.0, file_count / 5) if file_count > 0 else 0.0
        if any("pyproject.toml" in e or "setup.py" in e for e in evidence):
            confidence = max(confidence, 0.9)

        return {
            "detected": file_count > 0 or len(evidence) > 0,
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "file_count": file_count,
        }

    def scan(self, repo_root: Path) -> dict[str, Any]:
        """Scan Python repository using existing scanner internals.

        Calls the internal scanning functions directly to avoid circular
        recursion through scan_repository() → registry → PythonScanner.scan().
        """
        from .repo_scanner import (
            _discover_python_files,
            _scan_modules,
            _scan_tests,
            _scan_dependencies,
            _scan_configuration,
            _scan_cli_entry_points,
            _scan_repository_metadata,
        )

        repo_info = _scan_repository_metadata(repo_root)
        py_files = _discover_python_files(repo_root)
        modules = _scan_modules(repo_root, py_files)
        tests = _scan_tests(repo_root, py_files, modules)
        deps = _scan_dependencies(repo_root)
        config = _scan_configuration(repo_root)
        cli_entries = _scan_cli_entry_points(repo_root)

        source_files = []
        for mod in modules:
            source_files.append({
                "path": mod.get("file_path", ""),
                "language": "python",
                "size": mod.get("lines_of_code", 0),
            })

        return {
            "repository": {**repo_info, "file_count": len(py_files)},
            "repository_languages": ["python"],
            "frameworks": [],
            "modules": modules,
            "source_files": source_files,
            "imports": [],
            "exports": [],
            "tests": tests,
            "dependencies": deps,
            "configuration": config,
            "cli_entry_points": cli_entries,
            "complexity_signals": [],
            "debt_signals": [],
        }
