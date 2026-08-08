"""Repository Intelligence — Scanner Abstraction Layer.

Defines the scanner interface and registry for multi-language support.
Each scanner exposes a uniform interface for detection and scanning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class RepositoryScanner(ABC):
    """Abstract base class for language-specific repository scanners."""

    @property
    @abstractmethod
    def scanner_id(self) -> str:
        """Unique identifier for this scanner."""

    @property
    @abstractmethod
    def supported_languages(self) -> tuple[str, ...]:
        """Language names this scanner handles."""

    @abstractmethod
    def detect(self, repo_root: Path) -> dict[str, Any]:
        """Detect whether this scanner applies to the repository.

        Returns dict with:
        - detected: bool
        - confidence: float (0.0-1.0)
        - evidence: list[str]
        - file_count: int
        """

    @abstractmethod
    def scan(self, repo_root: Path) -> dict[str, Any]:
        """Scan the repository and return canonical results.

        Returns dict conforming to Repository Intelligence schema.
        """

    def metadata(self) -> dict[str, Any]:
        """Return scanner metadata."""
        return {
            "scanner_id": self.scanner_id,
            "supported_languages": list(self.supported_languages),
            "version": "1.0",
        }


class ScannerRegistry:
    """Registry of available repository scanners."""

    def __init__(self) -> None:
        self._scanners: dict[str, RepositoryScanner] = {}

    def register(self, scanner: RepositoryScanner) -> None:
        """Register a scanner."""
        self._scanners[scanner.scanner_id] = scanner

    def get(self, scanner_id: str) -> RepositoryScanner | None:
        """Get a scanner by ID."""
        return self._scanners.get(scanner_id)

    def detect(self, repo_root: Path) -> list[dict[str, Any]]:
        """Run detection across all registered scanners.

        Returns list of detection results sorted by confidence (descending).
        """
        results: list[dict[str, Any]] = []
        for scanner in self._scanners.values():
            try:
                result = scanner.detect(repo_root)
                result["scanner_id"] = scanner.scanner_id
                result["languages"] = list(scanner.supported_languages)
                results.append(result)
            except Exception:
                results.append({
                    "scanner_id": scanner.scanner_id,
                    "detected": False,
                    "confidence": 0.0,
                    "evidence": ["detection failed"],
                    "file_count": 0,
                })
        return sorted(results, key=lambda r: r.get("confidence", 0), reverse=True)

    def scan(self, repo_root: Path, languages: list[str] | None = None) -> dict[str, Any]:
        """Scan repository using appropriate scanners.

        If languages is None, auto-detect and scan all detected languages.
        If languages is specified, only use scanners for those languages.
        """
        if languages is not None:
            # Filter scanners by requested languages
            lang_set = set(languages)
            scanners = [
                s for s in self._scanners.values()
                if lang_set & set(s.supported_languages)
            ]
        else:
            # Auto-detect
            detections = self.detect(repo_root)
            detected_ids = {d["scanner_id"] for d in detections if d.get("detected", False)}
            scanners = [s for s in self._scanners.values() if s.scanner_id in detected_ids]
            if not scanners:
                # Fallback: try all scanners
                scanners = list(self._scanners.values())

        # Run scanners and merge results
        all_modules: list[dict[str, Any]] = []
        all_files: list[dict[str, Any]] = []
        all_imports: list[dict[str, Any]] = []
        all_exports: list[dict[str, Any]] = []
        all_tests: dict[str, Any] = {"total_test_classes": 0, "total_test_functions": 0, "test_files": []}
        all_deps: dict[str, Any] = {}
        all_config: list[dict[str, Any]] = []
        all_cli: list[dict[str, Any]] = []
        all_complexity: list[dict[str, Any]] = []
        all_debt: list[dict[str, Any]] = []
        languages_detected: list[str] = []
        frameworks_detected: list[str] = []
        total_files = 0

        for scanner in scanners:
            try:
                result = scanner.scan(repo_root)
                all_modules.extend(result.get("modules", []))
                all_files.extend(result.get("source_files", []))
                all_imports.extend(result.get("imports", []))
                all_exports.extend(result.get("exports", []))

                test_data = result.get("tests", {})
                all_tests["total_test_classes"] += test_data.get("total_test_classes", 0)
                all_tests["total_test_functions"] += test_data.get("total_test_functions", 0)
                all_tests["test_files"].extend(test_data.get("test_files", []))
                # Merge Python-specific test fields if present
                if "test_modules" in test_data:
                    all_tests.setdefault("test_modules", []).extend(test_data["test_modules"])
                if "modules_with_tests" in test_data:
                    all_tests.setdefault("modules_with_tests", []).extend(test_data["modules_with_tests"])
                if "modules_without_tests" in test_data:
                    all_tests.setdefault("modules_without_tests", []).extend(test_data["modules_without_tests"])

                # Merge dependencies
                for lang, deps in result.get("dependencies", {}).items():
                    if lang not in all_deps:
                        all_deps[lang] = deps
                    elif isinstance(deps, dict) and isinstance(all_deps[lang], dict):
                        all_deps[lang].update(deps)

                all_config.extend(result.get("configuration", []))
                all_cli.extend(result.get("cli_entry_points", []))
                all_complexity.extend(result.get("complexity_signals", []))
                all_debt.extend(result.get("debt_signals", []))

                languages_detected.extend(result.get("repository_languages", []))
                frameworks_detected.extend(result.get("frameworks", []))
                total_files += result.get("repository", {}).get("file_count", 0)
            except Exception:
                continue

        return {
            "repository_languages": list(set(languages_detected)),
            "frameworks": list(set(frameworks_detected)),
            "source_files": all_files,
            "imports": all_imports,
            "exports": all_exports,
            "modules": all_modules,
            "tests": all_tests,
            "dependencies": all_deps,
            "configuration": all_config,
            "cli_entry_points": all_cli,
            "complexity_signals": all_complexity,
            "debt_signals": all_debt,
            "_total_files": total_files,
        }

    def list_scanners(self) -> list[dict[str, Any]]:
        """List all registered scanners."""
        return [s.metadata() for s in self._scanners.values()]


# Global registry instance
_registry: ScannerRegistry | None = None


def get_registry() -> ScannerRegistry:
    """Get the global scanner registry, initializing if needed."""
    global _registry
    if _registry is None:
        _registry = ScannerRegistry()
        _register_default_scanners(_registry)
    return _registry


def _register_default_scanners(registry: ScannerRegistry) -> None:
    """Register the default set of scanners."""
    from .python_scanner import PythonScanner
    from .js_scanner import JavaScriptScanner

    registry.register(PythonScanner())
    registry.register(JavaScriptScanner())
