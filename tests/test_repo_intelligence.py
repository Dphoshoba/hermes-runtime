"""Comprehensive tests for Repository Intelligence v0.1.

Covers: scanner, analyzer, renderer, CLI, determinism, and sample-repo validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_v01.repo_intel_models import (
    ArchitectureSummary,
    ClassInfo,
    CLIEntryPoint,
    ComplexitySignal,
    ConfigurationFile,
    DebtSignal,
    DependencyInfo,
    DependencyIntelligence,
    FunctionInfo,
    ImportInfo,
    ModuleGraph,
    ModuleInfo,
    PublicAPI,
    RepositoryIntelligence,
    TestModuleInfo,
)
from hermes_v01.repo_scanner import scan_repository
from hermes_v01.repo_analyzer import analyze_repository
from hermes_v01.repo_renderer import render_json, render_markdown, save_artifacts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_REPO = Path(__file__).resolve().parent.parent / "validation" / "sample-repo"
HERMES_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_repo_path() -> Path:
    return SAMPLE_REPO


@pytest.fixture
def hermes_root() -> Path:
    return HERMES_ROOT


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    d = tmp_path / "repo-intel"
    d.mkdir()
    return d


@pytest.fixture
def sample_scan(sample_repo_path: Path):
    return scan_repository(sample_repo_path)


@pytest.fixture
def sample_intel(sample_repo_path: Path):
    scan = scan_repository(sample_repo_path)
    return analyze_repository(scan)


# ---------------------------------------------------------------------------
# Scanner — Module Discovery
# ---------------------------------------------------------------------------

class TestScannerModuleDiscovery:
    def test_finds_python_modules(self, sample_scan: dict):
        modules = sample_scan["modules"]
        assert len(modules) >= 1
        names = {m["name"] for m in modules}
        assert "__init__" in names

    def test_module_has_path(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            assert "path" in mod
            assert mod["path"].endswith(".py")

    def test_module_has_size(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            assert "ast_size" in mod
            assert mod["ast_size"] >= 0

    def test_module_has_line_count(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            assert "line_count" in mod
            assert mod["line_count"] >= 0

    def test_module_has_package(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            path = mod.get("path", "")
            # Root-level modules don't have a package key
            if "/" in path or "\\" in path:
                assert "package" in mod, f"Module {path} should have a package key"
                assert len(mod["package"]) > 0


# ---------------------------------------------------------------------------
# Scanner — Class/Function Extraction
# ---------------------------------------------------------------------------

class TestScannerClassesAndFunctions:
    def test_classes_extracted(self, sample_scan: dict):
        all_classes = []
        for mod in sample_scan["modules"]:
            all_classes.extend(mod.get("classes", []))
        assert len(all_classes) >= 1

    def test_class_has_methods(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            for cls in mod.get("classes", []):
                assert "methods" in cls
                assert isinstance(cls["methods"], list)

    def test_method_has_signature(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            for cls in mod.get("classes", []):
                for method in cls.get("methods", []):
                    assert "signature" in method
                    assert method["signature"].startswith("(")

    def test_functions_extracted(self, sample_scan: dict):
        all_funcs = []
        for mod in sample_scan["modules"]:
            all_funcs.extend(mod.get("functions", []))
        assert len(all_funcs) >= 1

    def test_function_has_signature(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            for func in mod.get("functions", []):
                assert "signature" in func
                assert func["signature"].startswith("(")

    def test_function_has_docstring(self, sample_scan: dict):
        for mod in sample_scan["modules"]:
            for func in mod.get("functions", []):
                assert "docstring" in func


# ---------------------------------------------------------------------------
# Scanner — Test Discovery
# ---------------------------------------------------------------------------

class TestScannerTestDiscovery:
    def test_test_modules_found(self, sample_scan: dict):
        tests = sample_scan["tests"]
        assert len(tests["test_modules"]) >= 1

    def test_test_module_has_target(self, sample_scan: dict):
        for tm in sample_scan["tests"]["test_modules"]:
            assert "imported_modules" in tm
            assert isinstance(tm["imported_modules"], list)

    def test_test_functions_counted(self, sample_scan: dict):
        for tm in sample_scan["tests"]["test_modules"]:
            assert "test_functions" in tm
            assert len(tm["test_functions"]) >= 1

    def test_total_test_functions(self, sample_scan: dict):
        total = sample_scan["tests"]["total_test_functions"]
        assert total >= 1

    def test_total_test_classes(self, sample_scan: dict):
        total = sample_scan["tests"]["total_test_classes"]
        assert total >= 1


# ---------------------------------------------------------------------------
# Scanner — Dependency Extraction
# ---------------------------------------------------------------------------

class TestScannerDependencies:
    def test_dependencies_found(self, sample_scan: dict):
        deps = sample_scan["dependencies"]
        assert len(deps["runtime"]) >= 1

    def test_dependency_has_name(self, sample_scan: dict):
        for dep in sample_scan["dependencies"]["runtime"]:
            assert "name" in dep
            assert len(dep["name"]) > 0

    def test_dependency_has_version(self, sample_scan: dict):
        for dep in sample_scan["dependencies"]["runtime"]:
            assert "version_spec" in dep

    def test_python_version_extracted(self, sample_scan: dict):
        deps = sample_scan["dependencies"]
        assert "python_version" in deps
        assert len(deps["python_version"]) > 0

    def test_build_backend_extracted(self, sample_scan: dict):
        deps = sample_scan["dependencies"]
        assert "build_backend" in deps


# ---------------------------------------------------------------------------
# Scanner — Configuration Discovery
# ---------------------------------------------------------------------------

class TestScannerConfigDiscovery:
    def test_config_files_found(self, sample_scan: dict):
        assert len(sample_scan["configuration"]) >= 1

    def test_config_has_path(self, sample_scan: dict):
        for cfg in sample_scan["configuration"]:
            assert "path" in cfg
            assert len(cfg["path"]) > 0

    def test_config_has_kind(self, sample_scan: dict):
        for cfg in sample_scan["configuration"]:
            assert "kind" in cfg
            assert len(cfg["kind"]) > 0


# ---------------------------------------------------------------------------
# Scanner — CLI Entry Points
# ---------------------------------------------------------------------------

class TestScannerCLIEntryPoints:
    def test_cli_entry_points_is_list(self, sample_scan: dict):
        assert isinstance(sample_scan["cli_entry_points"], list)

    def test_cli_entry_has_name_target(self, sample_scan: dict):
        for ep in sample_scan["cli_entry_points"]:
            assert "name" in ep
            assert "target" in ep
            assert len(ep["name"]) > 0
            assert len(ep["target"]) > 0


# ---------------------------------------------------------------------------
# Analyzer — Module Graph
# ---------------------------------------------------------------------------

class TestAnalyzerModuleGraph:
    def test_graph_has_nodes(self, sample_intel: RepositoryIntelligence):
        assert len(sample_intel.module_graph.nodes) >= 1

    def test_graph_edge_is_tuple(self, sample_intel: RepositoryIntelligence):
        for edge in sample_intel.module_graph.edges:
            assert isinstance(edge, tuple)
            assert len(edge) == 2

    def test_import_cycles_is_tuple(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.module_graph.import_cycles, tuple)

    def test_isolated_modules_is_tuple(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.module_graph.isolated_modules, tuple)

    def test_highly_connected_is_tuple(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.module_graph.highly_connected_modules, tuple)


# ---------------------------------------------------------------------------
# Analyzer — Public API
# ---------------------------------------------------------------------------

class TestAnalyzerPublicAPI:
    def test_api_classes(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.public_api.classes, tuple)

    def test_api_functions(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.public_api.functions, tuple)

    def test_class_has_name(self, sample_intel: RepositoryIntelligence):
        for cls in sample_intel.public_api.classes:
            assert len(cls.name) > 0

    def test_function_has_name(self, sample_intel: RepositoryIntelligence):
        for func in sample_intel.public_api.functions:
            assert len(func.name) > 0

    def test_class_methods_have_visibility(self, sample_intel: RepositoryIntelligence):
        for cls in sample_intel.public_api.classes:
            for method in cls.methods:
                assert hasattr(method, "is_public")


# ---------------------------------------------------------------------------
# Analyzer — Complexity Signals
# ---------------------------------------------------------------------------

class TestAnalyzerComplexity:
    def test_signals_are_tuple(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.complexity_signals, (tuple, list))

    def test_signals_have_severity(self, sample_intel: RepositoryIntelligence):
        for sig in sample_intel.complexity_signals:
            assert sig.severity in ("low", "medium", "high", "critical")

    def test_signals_have_target(self, sample_intel: RepositoryIntelligence):
        for sig in sample_intel.complexity_signals:
            assert len(sig.target) > 0

    def test_signals_have_message(self, sample_intel: RepositoryIntelligence):
        for sig in sample_intel.complexity_signals:
            assert len(sig.message) > 0


# ---------------------------------------------------------------------------
# Analyzer — Debt Signals
# ---------------------------------------------------------------------------

class TestAnalyzerDebt:
    def test_debt_are_tuple(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.technical_debt_signals, (tuple, list))

    def test_debt_have_severity(self, sample_intel: RepositoryIntelligence):
        for sig in sample_intel.technical_debt_signals:
            assert sig.severity in ("info", "low", "medium", "high", "critical")

    def test_debt_have_evidence(self, sample_intel: RepositoryIntelligence):
        for sig in sample_intel.technical_debt_signals:
            assert len(sig.evidence) > 0


# ---------------------------------------------------------------------------
# Analyzer — Architecture Summary
# ---------------------------------------------------------------------------

class TestAnalyzerArchitecture:
    def test_summary_counts(self, sample_intel: RepositoryIntelligence):
        arch = sample_intel.architecture_summary
        assert arch.module_count >= 1
        assert arch.function_count >= 1

    def test_summary_packages(self, sample_intel: RepositoryIntelligence):
        assert isinstance(sample_intel.architecture_summary.packages, tuple)

    def test_summary_repository_name(self, sample_intel: RepositoryIntelligence):
        assert len(sample_intel.architecture_summary.repository_name) > 0


# ---------------------------------------------------------------------------
# Renderer — JSON
# ---------------------------------------------------------------------------

class TestRendererJSON:
    def test_json_is_valid(self, sample_intel: RepositoryIntelligence):
        raw = render_json(sample_intel)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_json_has_schema_version(self, sample_intel: RepositoryIntelligence):
        data = json.loads(render_json(sample_intel))
        assert "schema_version" in data

    def test_json_roundtrip(self, sample_intel: RepositoryIntelligence):
        raw = render_json(sample_intel)
        data = json.loads(raw)
        raw2 = json.dumps(data, indent=2, sort_keys=True)
        assert raw == raw2


# ---------------------------------------------------------------------------
# Renderer — Markdown
# ---------------------------------------------------------------------------

class TestRendererMarkdown:
    def test_markdown_has_header(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert md.startswith("# Repository Intelligence")

    def test_markdown_has_architecture(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert "## Architecture Summary" in md

    def test_markdown_has_public_api(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert "## Public API" in md

    def test_markdown_has_module_graph(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert "## Module Graph" in md

    def test_markdown_has_tests(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert "## Test Intelligence" in md

    def test_markdown_has_dependencies(self, sample_intel: RepositoryIntelligence):
        md = render_markdown(sample_intel)
        assert "## Dependencies" in md


# ---------------------------------------------------------------------------
# Renderer — Save Artifacts
# ---------------------------------------------------------------------------

class TestRendererSaveArtifacts:
    def test_creates_json_and_md(self, sample_intel: RepositoryIntelligence, tmp_output: Path):
        json_path, md_path = save_artifacts(sample_intel, tmp_output)
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "REPOSITORY_INTELLIGENCE.json"
        assert md_path.name == "REPOSITORY_INTELLIGENCE.md"

    def test_json_is_valid_file(self, sample_intel: RepositoryIntelligence, tmp_output: Path):
        json_path, _ = save_artifacts(sample_intel, tmp_output)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "schema_version" in data

    def test_md_starts_with_header(self, sample_intel: RepositoryIntelligence, tmp_output: Path):
        _, md_path = save_artifacts(sample_intel, tmp_output)
        content = md_path.read_text(encoding="utf-8")
        assert content.startswith("# Repository Intelligence")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_scan_deterministic(self, sample_repo_path: Path):
        s1 = scan_repository(sample_repo_path)
        s2 = scan_repository(sample_repo_path)
        assert s1 == s2

    def test_analyze_deterministic(self, sample_repo_path: Path):
        s1 = scan_repository(sample_repo_path)
        s2 = scan_repository(sample_repo_path)
        i1 = analyze_repository(s1)
        i2 = analyze_repository(s2)
        assert render_json(i1) == render_json(i2)


# ---------------------------------------------------------------------------
# CLI Integration
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "hermes_v01.repo_cli", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_scan(self, sample_repo_path: Path, tmp_output: Path):
        result = self._run([
            "--repo", str(sample_repo_path),
            "--output-dir", str(tmp_output),
            "scan",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "scanned"

    def test_show(self, sample_repo_path: Path, tmp_output: Path):
        self._run([
            "--repo", str(sample_repo_path),
            "--output-dir", str(tmp_output),
            "scan",
        ])
        result = self._run([
            "--repo", str(sample_repo_path),
            "--output-dir", str(tmp_output),
            "show",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "schema_version" in data

    def test_check_current(self, sample_repo_path: Path, tmp_output: Path):
        self._run([
            "--repo", str(sample_repo_path),
            "--output-dir", str(tmp_output),
            "scan",
        ])
        result = self._run([
            "--repo", str(sample_repo_path),
            "--output-dir", str(tmp_output),
            "check",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["current"] is True

    def test_check_stale(self, sample_repo_path: Path, tmp_output: Path):
        (sample_repo_path / "ephemeral.py").write_text("# stale\n")
        try:
            self._run([
                "--repo", str(sample_repo_path),
                "--output-dir", str(tmp_output),
                "scan",
            ])
            (sample_repo_path / "ephemeral2.py").write_text("# changed\n")
            result = self._run([
                "--repo", str(sample_repo_path),
                "--output-dir", str(tmp_output),
                "check",
            ])
            assert result.returncode == 1
            data = json.loads(result.stdout)
            assert data["current"] is False
        finally:
            (sample_repo_path / "ephemeral.py").unlink(missing_ok=True)
            (sample_repo_path / "ephemeral2.py").unlink(missing_ok=True)

    def test_summary(self, sample_repo_path: Path):
        result = self._run([
            "--repo", str(sample_repo_path),
            "summary",
        ])
        assert result.returncode == 0
        assert "# Repository Intelligence" in result.stdout


# ---------------------------------------------------------------------------
# Hermes Self-Scan (Dogfooding)
# ---------------------------------------------------------------------------

class TestHermesSelfScan:
    def test_scan_hermes_self(self, hermes_root: Path):
        scan = scan_repository(hermes_root)
        intel = analyze_repository(scan)

        # Must find core modules by path
        module_paths = {m.path for m in intel.modules}
        assert any("hermes_v01" in p for p in module_paths)

        # Must find core classes
        class_names = {cls.name for cls in intel.public_api.classes}
        assert "WorkQueueManager" in class_names

        # Must find CLI entry points
        ep_names = {ep.name for ep in intel.public_api.cli_entry_points}
        assert "hermes-plan" in ep_names
        assert "hermes-repo" in ep_names

        # Must find dependencies
        dep_names = {d.name for d in intel.dependencies.runtime}
        assert len(dep_names) >= 1

        # Must produce valid JSON
        raw = render_json(intel)
        data = json.loads(raw)
        assert "schema_version" in data

    def test_hermes_markdown_readable(self, hermes_root: Path):
        scan = scan_repository(hermes_root)
        intel = analyze_repository(scan)
        md = render_markdown(intel)
        assert "## Architecture Summary" in md
        assert "## Public API" in md
        assert "## Module Graph" in md
        assert "## Test Intelligence" in md
        assert "## Dependencies" in md

    def test_hermes_artifacts_saved(self, hermes_root: Path, tmp_output: Path):
        scan = scan_repository(hermes_root)
        intel = analyze_repository(scan)
        json_path, md_path = save_artifacts(intel, tmp_output)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["architecture_summary"]["module_count"] >= 20
