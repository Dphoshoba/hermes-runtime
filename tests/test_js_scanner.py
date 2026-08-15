"""Comprehensive tests for JavaScript/TypeScript Scanner.

Covers: language detection, JS/TS parsing, React detection, frontend intelligence,
robustness, determinism, and zero-Python-findings acceptance criterion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evosia.js_scanner import JavaScriptScanner
from evosia.language_detector import detect_languages, detect_project_type
from evosia.repo_analyzer import analyze_repository
from evosia.repo_scanner import scan_repository
from evosia.scanner_registry import ScannerRegistry, get_registry

FIXTURES = Path(__file__).resolve().parent / "fixtures"
JS_REPO = FIXTURES / "js-repo"
TS_REPO = FIXTURES / "ts-repo"
MIXED_REPO = FIXTURES / "mixed-repo"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def js_scanner():
    return JavaScriptScanner()


@pytest.fixture
def js_repo_scan(js_scanner):
    return js_scanner.scan(JS_REPO)


@pytest.fixture
def ts_repo_scan(js_scanner):
    return js_scanner.scan(TS_REPO)


@pytest.fixture
def registry():
    return get_registry()


# ---------------------------------------------------------------------------
# Language Detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:
    def test_js_only_repo(self):
        result = detect_languages(JS_REPO)
        langs = {l["language"] for l in result["languages"]}
        assert "javascript" in langs

    def test_ts_only_repo(self):
        result = detect_languages(TS_REPO)
        langs = {l["language"] for l in result["languages"]}
        assert "typescript" in langs

    def test_mixed_js_ts(self):
        result = detect_languages(JS_REPO)
        langs = {l["language"] for l in result["languages"]}
        assert "javascript" in langs
        assert "typescript" in langs

    def test_python_js_mixed_repo(self):
        result = detect_languages(MIXED_REPO)
        langs = {l["language"] for l in result["languages"]}
        assert "python" in langs
        assert "javascript" in langs

    def test_react_detection(self):
        result = detect_languages(JS_REPO)
        frameworks = {f["framework"] for f in result["frameworks"]}
        assert "react" in frameworks

    def test_primary_language(self):
        result = detect_languages(JS_REPO)
        assert result["primary_language"] in ("javascript", "typescript")

    def test_file_counts(self):
        result = detect_languages(JS_REPO)
        assert result["file_counts"].get("javascript", 0) > 0

    def test_project_type_react(self):
        result = detect_project_type(JS_REPO)
        assert result["project_type"] == "react"

    def test_project_type_node(self):
        result = detect_project_type(TS_REPO)
        assert result["project_type"] in ("node", "unknown")


# ---------------------------------------------------------------------------
# JavaScriptScanner Detection
# ---------------------------------------------------------------------------

class TestScannerDetection:
    def test_detects_js_repo(self, js_scanner):
        result = js_scanner.detect(JS_REPO)
        assert result["detected"] is True
        assert result["confidence"] > 0
        assert result["file_count"] > 0

    def test_detects_ts_repo(self, js_scanner):
        result = js_scanner.detect(TS_REPO)
        assert result["detected"] is True
        assert result["confidence"] > 0

    def test_no_detection_for_python_only(self, js_scanner, tmp_path):
        (tmp_path / "app.py").write_text("print('hello')")
        result = js_scanner.detect(tmp_path)
        assert result["detected"] is False

    def test_scanner_id(self, js_scanner):
        assert js_scanner.scanner_id == "javascript"

    def test_supported_languages(self, js_scanner):
        assert "javascript" in js_scanner.supported_languages
        assert "typescript" in js_scanner.supported_languages


# ---------------------------------------------------------------------------
# JavaScript Parsing — Imports
# ---------------------------------------------------------------------------

class TestJSParsingImports:
    def test_imports_found(self, js_repo_scan):
        all_imports = []
        for mod in js_repo_scan["modules"]:
            all_imports.extend(mod.get("imports", []))
        assert len(all_imports) > 0

    def test_esm_import(self, js_repo_scan):
        all_imports = []
        for mod in js_repo_scan["modules"]:
            all_imports.extend(mod.get("imports", []))
        sources = {i["source"] for i in all_imports}
        assert "react" in sources

    def test_named_import(self, js_repo_scan):
        all_imports = []
        for mod in js_repo_scan["modules"]:
            all_imports.extend(mod.get("imports", []))
        sources = {i["source"] for i in all_imports}
        assert "react-router-dom" in sources

    def test_relative_import(self, js_repo_scan):
        all_imports = []
        for mod in js_repo_scan["modules"]:
            all_imports.extend(mod.get("imports", []))
        local_imports = [i for i in all_imports if i["source"].startswith(".")]
        assert len(local_imports) > 0

    def test_import_type(self, js_repo_scan):
        all_imports = []
        for mod in js_repo_scan["modules"]:
            all_imports.extend(mod.get("imports", []))
        for imp in all_imports:
            assert imp["type"] in ("esm", "commonjs")


# ---------------------------------------------------------------------------
# JavaScript Parsing — Exports
# ---------------------------------------------------------------------------

class TestJSParsingExports:
    def test_exports_found(self, js_repo_scan):
        assert len(js_repo_scan["exports"]) > 0

    def test_default_export(self, js_repo_scan):
        # Default exports can be named exports with "default" keyword
        all_exports = js_repo_scan["exports"]
        # Check that we have exports from components
        component_exports = [e for e in all_exports if "App" in e["name"] or "default" in e["name"]]
        assert len(component_exports) > 0

    def test_named_export(self, js_repo_scan):
        named = [e for e in js_repo_scan["exports"] if e["name"] != "default"]
        assert len(named) > 0


# ---------------------------------------------------------------------------
# JavaScript Parsing — Functions
# ---------------------------------------------------------------------------

class TestJSParsingFunctions:
    def test_functions_found(self, js_repo_scan):
        assert len(js_repo_scan["functions"]) > 0

    def test_function_has_name(self, js_repo_scan):
        for func in js_repo_scan["functions"]:
            assert "name" in func
            assert len(func["name"]) > 0

    def test_function_has_file(self, js_repo_scan):
        for func in js_repo_scan["functions"]:
            assert "file" in func

    def test_function_has_params(self, js_repo_scan):
        for func in js_repo_scan["functions"]:
            assert "params" in func
            assert isinstance(func["params"], list)

    def test_async_function(self, js_repo_scan):
        async_funcs = [f for f in js_repo_scan["functions"] if f.get("is_async")]
        assert len(async_funcs) > 0


# ---------------------------------------------------------------------------
# JavaScript Parsing — Classes
# ---------------------------------------------------------------------------

class TestJSParsingClasses:
    def test_classes_or_functions_found(self, js_repo_scan):
        # The fixture uses function components, not ES6 classes
        assert len(js_repo_scan["classes"]) > 0 or len(js_repo_scan["functions"]) > 0

    def test_class_has_name(self, js_repo_scan):
        for cls in js_repo_scan["classes"]:
            assert "name" in cls


# ---------------------------------------------------------------------------
# React Detection
# ---------------------------------------------------------------------------

class TestReactDetection:
    def test_components_found(self, js_repo_scan):
        assert len(js_repo_scan["components"]) > 0

    def test_component_has_name(self, js_repo_scan):
        for comp in js_repo_scan["components"]:
            assert "name" in comp
            assert comp["name"][0].isupper()  # React components start with uppercase

    def test_function_component(self, js_repo_scan):
        func_comps = [c for c in js_repo_scan["components"] if c["type"] == "function"]
        assert len(func_comps) > 0

    def test_hooks_detected(self, js_repo_scan):
        assert len(js_repo_scan["hooks"]) > 0

    def test_custom_hook(self, js_repo_scan):
        custom_hooks = [h for h in js_repo_scan["hooks"] if h.get("is_custom")]
        # useCustomHook should be detected as custom
        hook_names = {h["name"] for h in js_repo_scan["hooks"]}
        assert "useCustomHook" in hook_names

    def test_memo_component(self, js_repo_scan):
        # Header component uses React.memo
        memo_comps = [c for c in js_repo_scan["components"] if c.get("is_memo")]
        assert len(memo_comps) > 0, (
            f"Expected memo components, got: "
            f"{[(c['name'], c.get('is_memo')) for c in js_repo_scan['components']]}"
        )

    def test_forward_ref_component(self, js_repo_scan):
        # ForwardRefComponent uses forwardRef
        fr_comps = [c for c in js_repo_scan["components"] if "forward" in c["name"].lower()]
        assert len(fr_comps) > 0


# ---------------------------------------------------------------------------
# Frontend/Package Intelligence
# ---------------------------------------------------------------------------

class TestFrontendIntelligence:
    def test_package_json_parsed(self, js_repo_scan):
        deps = js_repo_scan.get("dependencies", {})
        assert "production" in deps or "development" in deps

    def test_runtime_dependencies(self, js_repo_scan):
        deps = js_repo_scan.get("dependencies", {})
        prod = deps.get("production", [])
        assert "react" in prod

    def test_dev_dependencies(self, js_repo_scan):
        deps = js_repo_scan.get("dependencies", {})
        dev = deps.get("development", [])
        assert any("jest" in d or "testing" in d for d in dev)

    def test_scripts(self, js_repo_scan):
        deps = js_repo_scan.get("dependencies", {})
        scripts = deps.get("scripts", {})
        assert "test" in scripts

    def test_configuration_files(self, js_repo_scan):
        config = js_repo_scan.get("configuration", [])
        config_names = {c["kind"] for c in config}
        assert "package.json" in config_names

    def test_fetch_api_calls(self, js_repo_scan):
        assert len(js_repo_scan.get("fetch_calls", [])) > 0

    def test_routes_detected(self, js_repo_scan):
        assert len(js_repo_scan.get("routes", [])) > 0


# ---------------------------------------------------------------------------
# TypeScript-Specific
# ---------------------------------------------------------------------------

class TestTypeScriptParsing:
    def test_ts_modules_found(self, ts_repo_scan):
        ts_modules = [m for m in ts_repo_scan["modules"] if m.get("language") == "typescript"]
        assert len(ts_modules) > 0

    def test_ts_config_detected(self, ts_repo_scan):
        config = ts_repo_scan.get("configuration", [])
        config_names = {c["kind"] for c in config}
        assert "tsconfig.json" in config_names

    def test_ts_dependencies(self, ts_repo_scan):
        deps = ts_repo_scan.get("dependencies", {})
        prod = deps.get("production", [])
        dev = deps.get("development", [])
        all_deps = prod + dev
        assert any("typescript" in d for d in all_deps)


# ---------------------------------------------------------------------------
# Mixed Language Scanning
# ---------------------------------------------------------------------------

class TestMixedLanguageScanning:
    def test_registry_detects_both(self, registry):
        detections = registry.detect(MIXED_REPO)
        detected = {d["scanner_id"] for d in detections if d.get("detected")}
        assert "python" in detected
        assert "javascript" in detected

    def test_registry_scans_both(self, registry):
        result = registry.scan(MIXED_REPO)
        langs = set(result.get("repository_languages", []))
        assert "python" in langs
        assert "javascript" in langs

    def test_mixed_modules(self, registry):
        result = registry.scan(MIXED_REPO)
        modules = result.get("modules", [])
        assert len(modules) > 0

    def test_scan_repository_mixed(self):
        result = scan_repository(MIXED_REPO)
        assert len(result.get("modules", [])) > 0


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_malformed_js(self, js_scanner, tmp_path):
        (tmp_path / "bad.js").write_text("function {{{{ broken }}")
        result = js_scanner.scan(tmp_path)
        assert "modules" in result

    def test_malformed_package_json(self, js_scanner, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text("{ invalid json }")
        (tmp_path / "app.js").write_text("import x from 'y';")
        result = js_scanner.scan(tmp_path)
        assert "modules" in result

    def test_unsupported_syntax(self, js_scanner, tmp_path):
        (tmp_path / "app.js").write_text("const x = `template ${'string'}`;")
        result = js_scanner.scan(tmp_path)
        assert len(result.get("modules", [])) > 0

    def test_empty_repo(self, js_scanner, tmp_path):
        result = js_scanner.scan(tmp_path)
        assert result["modules"] == []
        assert result["repository"]["file_count"] == 0

    def test_no_package_json(self, js_scanner, tmp_path):
        (tmp_path / "app.js").write_text("console.log('hello');")
        result = js_scanner.scan(tmp_path)
        assert len(result.get("modules", [])) > 0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self, js_scanner):
        result1 = js_scanner.scan(JS_REPO)
        result2 = js_scanner.scan(JS_REPO)
        assert json.dumps(result1, sort_keys=True) == json.dumps(result2, sort_keys=True)

    def test_scan_repository_deterministic(self):
        result1 = scan_repository(JS_REPO)
        result2 = scan_repository(JS_REPO)
        assert json.dumps(result1, sort_keys=True) == json.dumps(result2, sort_keys=True)


# ---------------------------------------------------------------------------
# Analyze Integration
# ---------------------------------------------------------------------------

class TestAnalyzeIntegration:
    def test_analyze_js_repo(self):
        scan = scan_repository(JS_REPO)
        intel = analyze_repository(scan)
        assert intel is not None

    def test_analyze_has_modules(self):
        scan = scan_repository(JS_REPO)
        intel = analyze_repository(scan)
        assert len(intel.modules) > 0

    def test_analyze_has_architecture_summary(self):
        scan = scan_repository(JS_REPO)
        intel = analyze_repository(scan)
        assert intel.architecture_summary is not None


# ---------------------------------------------------------------------------
# Zero Python Findings Acceptance Criterion
# ---------------------------------------------------------------------------

class TestZeroPythonFindings:
    """A JS/React-only repository must generate ZERO Python packaging findings
    unless genuine Python artifacts are present."""

    def _get_engineering_intel(self):
        """Run full pipeline to get engineering intelligence with findings."""
        from evosia.engineering_analyzer import analyze_engineering
        scan = scan_repository(JS_REPO)
        return analyze_engineering(scan)

    def test_no_python_config_findings(self):
        ei = self._get_engineering_intel()
        config_findings = [f for f in ei.findings if f.category == "Configuration"]
        python_config = [
            f for f in config_findings
            if "pyproject" in f.title.lower() or "python" in f.title.lower()
        ]
        assert len(python_config) == 0, (
            f"JS-only repo should not have Python config findings, got: "
            f"{[f.title for f in python_config]}"
        )

    def test_no_python_dependency_findings(self):
        ei = self._get_engineering_intel()
        dep_findings = [f for f in ei.findings if f.category == "Dependencies"]
        python_deps = [
            f for f in dep_findings
            if "python" in f.title.lower() or "pyproject" in f.title.lower()
        ]
        assert len(python_deps) == 0, (
            f"JS-only repo should not have Python dependency findings, got: "
            f"{[f.title for f in python_deps]}"
        )

    def test_no_python_packaging_findings(self):
        ei = self._get_engineering_intel()
        pkg_findings = [f for f in ei.findings if f.category == "Packaging"]
        python_pkg = [
            f for f in pkg_findings
            if "python" in f.title.lower() or "pyproject" in f.title.lower()
        ]
        assert len(python_pkg) == 0, (
            f"JS-only repo should not have Python packaging findings, got: "
            f"{[f.title for f in python_pkg]}"
        )

    def test_js_repo_has_valid_findings(self):
        ei = self._get_engineering_intel()
        valid_categories = {
            "Architecture", "Coupling", "Complexity", "Documentation",
            "Testing", "Configuration", "Dependencies", "CLI",
            "Public API", "Performance", "Maintainability", "Security Signals",
            "Technical Debt",
        }
        for finding in ei.findings:
            assert finding.category in valid_categories, (
                f"Unexpected category: {finding.category}"
            )


# ---------------------------------------------------------------------------
# DEFECT 1 Regression: .gitignore detection in JS/TS repos
# ---------------------------------------------------------------------------

class TestGitignoreDetection:
    """Verify .gitignore is detected by JS scanner and no false positive."""

    def test_js_repo_detects_gitignore(self, js_scanner):
        result = js_scanner.scan(JS_REPO)
        config_kinds = {c["kind"] for c in result.get("configuration", [])}
        assert ".gitignore" in config_kinds, (
            f"JS scanner should detect .gitignore, got config: {config_kinds}"
        )

    def test_ts_repo_detects_gitignore(self, js_scanner):
        result = js_scanner.scan(TS_REPO)
        config_kinds = {c["kind"] for c in result.get("configuration", [])}
        assert ".gitignore" in config_kinds, (
            f"TS scanner should detect .gitignore, got config: {config_kinds}"
        )

    def test_no_false_missing_gitignore_when_present(self):
        """Engineering Intelligence should not flag .gitignore when it exists."""
        from evosia.engineering_analyzer import analyze_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        gitignore_findings = [
            f for f in ei.findings
            if f.category == "Configuration" and ".gitignore" in f.title
        ]
        assert len(gitignore_findings) == 0, (
            f"Should not have missing .gitignore finding when file exists, "
            f"got: {[f.title for f in gitignore_findings]}"
        )

    def test_missing_gitignore_generates_finding(self, tmp_path):
        """When .gitignore is absent, a finding should be generated."""
        from evosia.engineering_analyzer import analyze_engineering
        repo = tmp_path / "no-gitignore-repo"
        repo.mkdir()
        (repo / "package.json").write_text('{"name": "test"}')
        (repo / "src").mkdir()
        (repo / "src" / "index.js").write_text("console.log('hello');")
        scan = scan_repository(repo)
        ei = analyze_engineering(scan)
        gitignore_findings = [
            f for f in ei.findings
            if f.category == "Configuration" and ".gitignore" in f.title
        ]
        assert len(gitignore_findings) == 1, (
            f"Should have exactly one missing .gitignore finding, "
            f"got: {[f.title for f in gitignore_findings]}"
        )

    def test_python_scanner_still_detects_gitignore(self):
        """Python scanner behavior unchanged — still detects .gitignore."""
        from evosia.repo_scanner import _scan_configuration
        from pathlib import Path
        # Use a temp dir with .gitignore
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / ".gitignore").write_text("*.pyc\n")
            config = _scan_configuration(p)
            kinds = {c["kind"] for c in config}
            assert ".gitignore" in kinds


# ---------------------------------------------------------------------------
# DEFECT 2 Regression: Frontend complexity evidence references
# ---------------------------------------------------------------------------

class TestFrontendEvidenceReferences:
    """Verify complexity findings have non-empty evidence references."""

    def test_complexity_findings_have_evidence(self):
        from evosia.engineering_analyzer import analyze_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        complexity_findings = [f for f in ei.findings if f.category == "Complexity"]
        for finding in complexity_findings:
            assert len(finding.evidence_references) > 0, (
                f"Complexity finding '{finding.title}' has no evidence references"
            )
            for ref in finding.evidence_references:
                assert ref.reference_path, (
                    f"Evidence reference missing reference_path in '{finding.title}'"
                )
                assert ref.detail, (
                    f"Evidence reference missing detail in '{finding.title}'"
                )

    def test_hook_concentration_evidence_has_component(self):
        """high_hook_concentration evidence should mention component name."""
        from evosia.engineering_analyzer import analyze_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        hook_findings = [
            f for f in ei.findings
            if f.category == "Complexity" and "hook" in f.title.lower()
        ]
        for finding in hook_findings:
            details = [ref.detail for ref in finding.evidence_references]
            assert any("hook" in d.lower() for d in details), (
                f"Hook concentration evidence should mention hooks, got: {details}"
            )

    def test_api_concentration_evidence_has_fetch_count(self):
        """api_concentration evidence should mention fetch/API call count."""
        from evosia.engineering_analyzer import analyze_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        api_findings = [
            f for f in ei.findings
            if f.category == "Complexity" and "api" in f.title.lower()
        ]
        for finding in api_findings:
            details = [ref.detail for ref in finding.evidence_references]
            assert any(
                "fetch" in d.lower() or "api" in d.lower() or "call" in d.lower()
                for d in details
            ), f"API concentration evidence should mention API calls, got: {details}"

    def test_js_scanner_signals_include_required_fields(self, js_scanner):
        """JS scanner complexity signals must include target, message, signal_type."""
        result = js_scanner.scan(JS_REPO)
        for sig in result.get("complexity_signals", []):
            assert "target" in sig, f"Signal missing 'target': {sig}"
            assert "message" in sig, f"Signal missing 'message': {sig}"
            assert "signal_type" in sig, f"Signal missing 'signal_type': {sig}"
            assert sig["target"], f"Signal 'target' is empty: {sig}"
            assert sig["message"], f"Signal 'message' is empty: {sig}"


# ---------------------------------------------------------------------------
# DEFECT 3 Regression: Governance traceability
# ---------------------------------------------------------------------------

class TestGovernanceTraceability:
    """Verify governance preserves evidence quality for frontend findings."""

    def test_governance_receives_evidence_quality(self):
        from evosia.engineering_analyzer import analyze_engineering
        from evosia.governance_analyzer import govern_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        gov = govern_engineering(ei.as_dict())
        for assessment in gov.assessment.recommendation_assessments:
            eq = assessment.evidence_quality
            assert eq.level in ("low", "medium", "high"), (
                f"Invalid evidence level: {eq.level}"
            )
            assert eq.reference_count >= 0, (
                f"Invalid reference count: {eq.reference_count}"
            )

    def test_approved_findings_have_evidence(self):
        """Every APPROVED frontend recommendation must have non-empty evidence."""
        from evosia.engineering_analyzer import analyze_engineering
        from evosia.governance_analyzer import govern_engineering
        scan = scan_repository(JS_REPO)
        ei = analyze_engineering(scan)
        gov = govern_engineering(ei.as_dict())
        findings_by_id = {f.finding_id: f for f in ei.findings}
        for decision in gov.assessment.approval_decisions:
            if decision.decision in ("APPROVED", "APPROVED_WITH_NOTES"):
                finding = findings_by_id.get(decision.finding_id)
                if finding and finding.category == "Complexity":
                    assert len(finding.evidence_references) > 0, (
                        f"Approved complexity finding '{finding.title}' "
                        f"has no evidence references"
                    )
