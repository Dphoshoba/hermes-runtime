"""Engineering Intelligence — analysis engine.

Consumes Repository Intelligence JSON and produces:
- Findings (evidence-backed observations)
- Recommendations (what to do about each finding)
- Candidate missions (grouped findings into actionable work)
- Risk assessment (repository-level risk)
- Summary (executive counts and health score)

This is a reasoning layer. It never scans, never modifies, never enqueues.
"""

from __future__ import annotations

import math
from typing import Any

from .engineering_intel_models import (
    AffectedComponent,
    CandidateMission,
    ConfidenceScore,
    EngineeringIntelligence,
    EngineeringSummary,
    EvidenceReference,
    Finding,
    PriorityScore,
    Recommendation,
    RiskAssessment,
)


# ---------------------------------------------------------------------------
# Severity / priority helpers
# ---------------------------------------------------------------------------

_SEVERITY_NORM: dict[str, float] = {
    "critical": 10.0,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.5,
    "info": 1.0,
}

_EFFORT_FROM_SCORE: list[tuple[float, str]] = [
    (8.0, "large"),
    (6.0, "medium"),
    (4.0, "small"),
    (0.0, "trivial"),
]

_RISK_FROM_SEVERITY: dict[str, str] = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "none",
    "info": "none",
}


def _compute_priority(
    impact: float,
    confidence: float,
    severity: str,
    scope: float,
) -> PriorityScore:
    """Compute priority score using documented formula."""
    sev = _SEVERITY_NORM.get(severity, 1.0)
    score = 0.40 * impact + 0.20 * (confidence * 10) + 0.25 * sev + 0.15 * scope
    score = max(0.0, min(10.0, score))
    return PriorityScore(
        score=round(score, 2),
        impact=round(impact, 2),
        confidence=round(confidence, 2),
        severity=round(sev, 2),
        scope=round(scope, 2),
        formula="0.40*impact + 0.20*(confidence*10) + 0.25*severity + 0.15*scope",
    )


def _effort_from_priority(score: float) -> str:
    for threshold, label in _EFFORT_FROM_SCORE:
        if score >= threshold:
            return label
    return "trivial"


def _risk_from_severity(severity: str) -> str:
    return _RISK_FROM_SEVERITY.get(severity, "none")


def _confidence_from_evidence_count(count: int) -> float:
    """More evidence → higher confidence, with diminishing returns."""
    if count <= 0:
        return 0.0
    if count == 1:
        return 0.5
    if count == 2:
        return 0.7
    if count == 3:
        return 0.8
    if count <= 5:
        return 0.9
    return 0.95


def _impact_from_affected(count: int, total_modules: int) -> float:
    """Scale impact by proportion of affected modules, capped at 10."""
    if total_modules <= 0:
        return 1.0
    ratio = count / total_modules
    # Logarithmic scale: 1 module → ~2, all modules → 10
    raw = 2.0 + 8.0 * (math.log(max(ratio, 0.01)) / math.log(1.0 / total_modules)) if total_modules > 1 else 2.0
    return max(1.0, min(10.0, raw))


def _scope_from_category(category: str, count: int) -> float:
    """Scope based on category breadth and count."""
    broad_categories = {"Architecture", "Coupling", "Dependencies", "Security Signals"}
    base = 6.0 if category in broad_categories else 3.0
    return min(10.0, base + count * 0.5)


# ---------------------------------------------------------------------------
# Finding generation — one function per category
# ---------------------------------------------------------------------------

def _findings_from_cycles(ri: dict[str, Any]) -> list[Finding]:
    """Import cycles → Architecture findings."""
    findings: list[Finding] = []
    graph = ri.get("module_graph", {})
    cycles = graph.get("import_cycles", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    for i, cycle in enumerate(cycles):
        cycle_str = " → ".join(cycle)
        first_mod = cycle[0].rsplit("/", 1)[-1]
        last_mod = cycle[-1].rsplit("/", 1)[-1]
        title_prefix = f"Import cycle: {first_mod}" if first_mod == last_mod else f"Import cycle between {first_mod} and {last_mod}"
        evidence = [
            EvidenceReference(
                source="module_graph",
                reference_path=cycle_str,
                detail=f"Import cycle of length {len(cycle)}: {cycle_str}",
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module",
                component_path=path,
                component_name=path.rsplit("/", 1)[-1],
            )
            for path in cycle
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = _impact_from_affected(len(cycle), mod_count)
        severity = "high" if len(cycle) <= 3 else "critical"

        findings.append(Finding(
            finding_id=f"FINDING-{i + 1:03d}",
            category="Architecture",
            severity=severity,
            confidence=confidence,
            title=title_prefix,
            explanation=f"Detected import cycle: {cycle_str}. Cycles create tight coupling and make modules hard to test, refactor, or reuse independently.",
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))
    return findings


def _findings_from_highly_connected(ri: dict[str, Any]) -> list[Finding]:
    """Highly connected modules → Coupling findings."""
    findings: list[Finding] = []
    graph = ri.get("module_graph", {})
    highly_connected = graph.get("highly_connected_modules", [])
    edges = graph.get("edges", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    # Build degree map
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for src, tgt in edges:
        out_degree[src] = out_degree.get(src, 0) + 1
        in_degree[tgt] = in_degree.get(tgt, 0) + 1

    for i, mod_path in enumerate(highly_connected):
        deg = in_degree.get(mod_path, 0) + out_degree.get(mod_path, 0)
        evidence = [
            EvidenceReference(
                source="module_graph",
                reference_path=mod_path,
                detail=f"Module has {deg} connections (in+out degree)",
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module",
                component_path=mod_path,
                component_name=mod_path.rsplit("/", 1)[-1],
            )
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = min(8.0, deg * 0.5)
        severity = "high" if deg > 10 else "medium"

        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Coupling",
            severity=severity,
            confidence=confidence,
            title=f"Highly connected module: {mod_path.rsplit('/', 1)[-1]}",
            explanation=f"Module {mod_path} has {deg} connections, indicating high coupling. Changes to this module may have cascading effects.",
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))
    return findings


def _findings_from_complexity(ri: dict[str, Any]) -> list[Finding]:
    """Complexity signals → Complexity findings."""
    findings: list[Finding] = []
    signals = ri.get("complexity_signals", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    for i, sig in enumerate(signals):
        target = sig.get("target", sig.get("file", ""))
        sev_raw = sig.get("severity", "low")
        severity = "medium" if sev_raw in ("warning", "medium") else "low"
        ref_path = target or sig.get("reference_path", "")
        detail = sig.get("message", sig.get("detail", ""))
        if not detail:
            # Build detail from available fields
            sig_type = sig.get("signal_type", sig.get("type", "complexity"))
            value = sig.get("value", "")
            threshold = sig.get("threshold", "")
            if value and threshold:
                detail = f"{sig_type}: {value} (threshold: {threshold})"
            else:
                detail = f"Complexity signal: {sig_type}"
        evidence = [
            EvidenceReference(
                source="complexity_signals",
                reference_path=ref_path,
                detail=detail,
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module" if "::" not in target else "function",
                component_path=target.split("::")[0] if "::" in target else target,
                component_name=target.rsplit("::", 1)[-1] if "::" in target else target.rsplit("/", 1)[-1],
            )
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = _impact_from_affected(1, mod_count)
        scope = _scope_from_category("Complexity", 1)

        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Complexity",
            severity=severity,
            confidence=confidence,
            title=f"{sig.get('signal_type', 'complexity').replace('_', ' ').title()}: {target.rsplit('/', 1)[-1]}",
            explanation=sig.get("message", "Complexity signal detected"),
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))
    return findings


def _findings_from_debt(ri: dict[str, Any]) -> list[Finding]:
    """Technical debt signals → Technical Debt findings."""
    findings: list[Finding] = []
    signals = ri.get("technical_debt_signals", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    for i, sig in enumerate(signals):
        target = sig.get("target", "")
        signal_type = sig.get("signal_type", "unknown")

        # Map signal_type to category
        category_map = {
            "missing_docstring": "Documentation",
            "missing_function_docstring": "Documentation",
            "no_tests": "Testing",
            "import_cycle": "Architecture",
            "isolated_module": "Coupling",
        }
        category = category_map.get(signal_type, "Technical Debt")

        sev_raw = sig.get("severity", "info")
        severity = "low" if sev_raw == "info" else sev_raw

        evidence = [
            EvidenceReference(
                source="debt_signals",
                reference_path=target,
                detail=sig.get("evidence", sig.get("message", "")),
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module" if "::" not in target else "function",
                component_path=target.split("::")[0] if "::" in target else target,
                component_name=target.rsplit("::", 1)[-1] if "::" in target else target.rsplit("/", 1)[-1],
            )
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = _impact_from_affected(1, mod_count)
        scope = _scope_from_category(category, 1)

        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category=category,
            severity=severity,
            confidence=confidence,
            title=f"{signal_type.replace('_', ' ').title()}: {target.rsplit('/', 1)[-1]}",
            explanation=sig.get("message", "Technical debt signal detected"),
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))
    return findings


def _findings_from_untested(ri: dict[str, Any]) -> list[Finding]:
    """Modules without tests → Testing findings."""
    findings: list[Finding] = []
    tests = ri.get("tests", {})
    untested = tests.get("modules_without_tests", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    for i, mod_path in enumerate(untested):
        evidence = [
            EvidenceReference(
                source="tests",
                reference_path=mod_path,
                detail=f"Module {mod_path} not referenced by any test module",
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module",
                component_path=mod_path,
                component_name=mod_path.rsplit("/", 1)[-1],
            )
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = _impact_from_affected(1, mod_count)
        scope = _scope_from_category("Testing", 1)

        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Testing",
            severity="low",
            confidence=confidence,
            title=f"No test coverage: {mod_path.rsplit('/', 1)[-1]}",
            explanation=f"Module {mod_path} has no test coverage. Untested code increases risk of regressions.",
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))
    return findings


def _findings_from_dependencies(ri: dict[str, Any]) -> list[Finding]:
    """Dependency analysis → Dependencies findings."""
    findings: list[Finding] = []
    deps = ri.get("dependencies", {})
    modules = ri.get("modules", [])
    mod_count = len(modules)

    runtime = deps.get("runtime", [])
    python_version = deps.get("python_version")
    build_backend = deps.get("build_backend")

    # Check for missing version pins
    unpinned = [d for d in runtime if not d.get("version_spec")]
    if unpinned:
        names = ", ".join(d.get("name", "?") for d in unpinned[:5])
        evidence = [
            EvidenceReference(
                source="dependencies",
                reference_path="pyproject.toml",
                detail=f"Unpinned dependencies: {names}",
            )
        ]
        confidence = 0.7
        impact = _impact_from_affected(1, mod_count)
        scope = 4.0
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Dependencies",
            severity="medium",
            confidence=confidence,
            title=f"Unpinned runtime dependencies: {names}",
            explanation=f"{len(unpinned)} runtime dependencies lack version constraints. This can lead to unexpected breakage.",
            evidence_references=tuple(evidence),
            affected_components=tuple(
                AffectedComponent(
                    component_type="dependency",
                    component_path="pyproject.toml",
                    component_name=d.get("name", "?"),
                )
                for d in unpinned[:5]
            ),
        ))

    # Check for missing python version - only for Python projects
    languages = set(ri.get("repository_languages", []))
    is_python = "python" in languages or bool(python_version) or bool(build_backend)

    if is_python and not python_version:
        evidence = [
            EvidenceReference(
                source="dependencies",
                reference_path="pyproject.toml",
                detail="No requires-python specified",
            )
        ]
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Dependencies",
            severity="low",
            confidence=0.6,
            title="No Python version constraint specified",
            explanation="No requires-python field in pyproject.toml. Users may attempt installation on unsupported Python versions.",
            evidence_references=tuple(evidence),
            affected_components=(
                AffectedComponent(component_type="dependency", component_path="pyproject.toml", component_name="python"),
            ),
        ))

    # Check for missing build backend - only for Python projects
    if is_python and not build_backend:
        evidence = [
            EvidenceReference(
                source="dependencies",
                reference_path="pyproject.toml",
                detail="No build-backend specified",
            )
        ]
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Packaging",
            severity="medium",
            confidence=0.8,
            title="No build backend configured",
            explanation="No build-backend in pyproject.toml. Package may not build correctly.",
            evidence_references=tuple(evidence),
            affected_components=(
                AffectedComponent(component_type="configuration", component_path="pyproject.toml", component_name="build-backend"),
            ),
        ))

    return findings


def _findings_from_config(ri: dict[str, Any]) -> list[Finding]:
    """Configuration analysis → Configuration findings."""
    findings: list[Finding] = []
    config = ri.get("configuration", [])
    config_kinds = {c.get("kind", "") for c in config}
    modules = ri.get("modules", [])
    mod_count = len(modules)

    # Determine languages from RI
    languages = set(ri.get("repository_languages", []))
    if not languages and modules:
        # Infer from module paths
        for m in modules[:10]:
            fp = m.get("file_path", "")
            if fp.endswith(".py"):
                languages.add("python")
            elif fp.endswith((".js", ".jsx", ".ts", ".tsx")):
                languages.add("javascript")
                languages.add("typescript")

    # Check for essential configs based on detected languages
    essential: dict[str, tuple[str, str]] = {}
    if "python" in languages:
        essential["pyproject.toml"] = ("Python project configuration", "medium")
    if "javascript" in languages or "typescript" in languages:
        essential["package.json"] = ("Node.js package manifest", "medium")
    # Universal
    essential[".gitignore"] = ("Git ignore rules", "low")

    for kind, (desc, severity) in essential.items():
        if kind not in config_kinds:
            evidence = [
                EvidenceReference(
                    source="configuration",
                    reference_path=kind,
                    detail=f"Missing essential configuration: {kind}",
                )
            ]
            findings.append(Finding(
                finding_id=f"FINDING-{len(findings) + 1:03d}",
                category="Configuration",
                severity=severity,
                confidence=0.8,
                title=f"Missing configuration: {kind}",
                explanation=f"Essential configuration file {kind} ({desc}) not found in repository.",
                evidence_references=tuple(evidence),
                affected_components=(
                    AffectedComponent(component_type="configuration", component_path=kind, component_name=kind),
                ),
            ))

    return findings


def _findings_from_cli(ri: dict[str, Any]) -> list[Finding]:
    """CLI analysis → CLI findings."""
    findings: list[Finding] = []
    public_api = ri.get("public_api", {})
    cli_points = public_api.get("cli_entry_points", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    # Check for large number of CLI entry points without docs
    if len(cli_points) > 10:
        names = ", ".join(ep.get("name", "?") for ep in cli_points[:5])
        evidence = [
            EvidenceReference(
                source="public_api",
                reference_path="pyproject.toml",
                detail=f"{len(cli_points)} CLI entry points registered",
            )
        ]
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="CLI",
            severity="info",
            confidence=0.6,
            title=f"{len(cli_points)} CLI entry points registered",
            explanation=f"Repository has {len(cli_points)} CLI entry points ({names}...). Ensure each is documented.",
            evidence_references=tuple(evidence),
            affected_components=tuple(
                AffectedComponent(
                    component_type="cli",
                    component_path=ep.get("target", ""),
                    component_name=ep.get("name", "?"),
                )
                for ep in cli_points[:5]
            ),
        ))

    return findings


def _findings_from_public_api(ri: dict[str, Any]) -> list[Finding]:
    """Public API analysis → Public API findings."""
    findings: list[Finding] = []
    public_api = ri.get("public_api", {})
    classes = public_api.get("classes", [])
    functions = public_api.get("functions", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    total_public = len(classes) + len(functions)

    # Check for large public surface
    if total_public > 50:
        evidence = [
            EvidenceReference(
                source="public_api",
                reference_path="public_api",
                detail=f"Public API surface: {len(classes)} classes, {len(functions)} functions",
            )
        ]
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Public API",
            severity="info",
            confidence=0.5,
            title=f"Large public API surface ({total_public} symbols)",
            explanation=f"Repository exposes {total_public} public symbols. Consider whether all are necessary.",
            evidence_references=tuple(evidence),
            affected_components=(
                AffectedComponent(component_type="module", component_path="public_api", component_name="public_api"),
            ),
        ))

    return findings


def _findings_from_maintainability(ri: dict[str, Any]) -> list[Finding]:
    """Large modules/classes → Maintainability findings."""
    findings: list[Finding] = []
    modules = ri.get("modules", [])
    mod_count = len(modules)

    large_modules = [m for m in modules if m.get("line_count", 0) > 500]
    for i, mod in enumerate(large_modules):
        path = mod.get("path", "")
        line_count = mod.get("line_count", 0)
        severity = "high" if line_count > 1000 else "medium"
        evidence = [
            EvidenceReference(
                source="modules",
                reference_path=path,
                detail=f"Module has {line_count} lines",
            )
        ]
        affected = [
            AffectedComponent(
                component_type="module",
                component_path=path,
                component_name=path.rsplit("/", 1)[-1],
            )
        ]
        confidence = _confidence_from_evidence_count(len(evidence))
        impact = _impact_from_affected(1, mod_count)
        scope = _scope_from_category("Maintainability", 1)

        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Maintainability",
            severity=severity,
            confidence=confidence,
            title=f"Large module: {path.rsplit('/', 1)[-1]} ({line_count} lines)",
            explanation=f"Module {path} has {line_count} lines. Large modules are harder to understand, test, and maintain.",
            evidence_references=tuple(evidence),
            affected_components=tuple(affected),
        ))

    return findings


def _findings_from_security(ri: dict[str, Any]) -> list[Finding]:
    """Dependency security signals → Security findings."""
    findings: list[Finding] = []
    deps = ri.get("dependencies", {})
    runtime = deps.get("runtime", [])
    modules = ri.get("modules", [])
    mod_count = len(modules)

    # Check for very old version patterns (basic heuristic)
    old_patterns = []
    for d in runtime:
        spec = d.get("version_spec", "")
        name = d.get("name", "")
        # No upper bound at all is a risk signal
        if spec and ">" in spec and "<" not in spec and "~" not in spec:
            old_patterns.append(d)

    if len(old_patterns) > 3:
        names = ", ".join(d.get("name", "?") for d in old_patterns[:5])
        evidence = [
            EvidenceReference(
                source="dependencies",
                reference_path="pyproject.toml",
                detail=f"Dependencies with no upper bound: {names}",
            )
        ]
        findings.append(Finding(
            finding_id=f"FINDING-{len(findings) + 1:03d}",
            category="Security Signals",
            severity="low",
            confidence=0.4,
            title=f"Dependencies with no upper bound: {names}",
            explanation=f"{len(old_patterns)} runtime dependencies have no upper version bound. This may allow incompatible major versions.",
            evidence_references=tuple(evidence),
            affected_components=tuple(
                AffectedComponent(
                    component_type="dependency",
                    component_path="pyproject.toml",
                    component_name=d.get("name", "?"),
                )
                for d in old_patterns[:5]
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

_RECOMMENDATION_TEMPLATES: dict[str, tuple[str, str, str, str]] = {
    # category: (recommendation, rationale_template, benefit, default_risk)
    "Architecture": (
        "Break import cycle via dependency inversion or shared interface",
        "Import cycles create tight coupling between {targets}.",
        "Decoupled modules are independently testable and replaceable",
        "medium",
    ),
    "Coupling": (
        "Decouple highly connected module by extracting shared interface",
        "Module {targets} has excessive connections.",
        "Reduced blast radius for changes, easier testing",
        "low",
    ),
    "Complexity": (
        "Refactor into smaller, focused functions",
        "Complexity detected at {targets}.",
        "Improved readability, testability, and maintainability",
        "low",
    ),
    "Documentation": (
        "Add comprehensive docstrings",
        "Missing documentation at {targets}.",
        "Improved developer onboarding and API understanding",
        "none",
    ),
    "Testing": (
        "Add test coverage for untested modules",
        "No tests found for {targets}.",
        "Reduced regression risk, safer refactoring",
        "none",
    ),
    "Packaging": (
        "Fix packaging configuration",
        "Packaging issue at {targets}.",
        "Correct package installation and distribution",
        "low",
    ),
    "Configuration": (
        "Add missing configuration files",
        "Missing configuration: {targets}.",
        "Consistent development environment and CI/CD",
        "none",
    ),
    "Dependencies": (
        "Pin dependency versions and audit",
        "Dependency concern at {targets}.",
        "Reproducible builds and reduced breakage risk",
        "low",
    ),
    "CLI": (
        "Document CLI entry points",
        "CLI entry points at {targets} need documentation.",
        "Improved usability and discoverability",
        "none",
    ),
    "Public API": (
        "Review and document public API surface",
        "Public API at {targets} needs review.",
        "Clear API contracts and reduced accidental usage",
        "none",
    ),
    "Performance": (
        "Optimize performance-critical code paths",
        "Performance concern at {targets}.",
        "Improved runtime performance",
        "medium",
    ),
    "Maintainability": (
        "Split large module/class into smaller units",
        "Maintainability issue at {targets}.",
        "Easier to understand, test, and modify",
        "medium",
    ),
    "Observability": (
        "Add logging, metrics, and monitoring",
        "Observability gap at {targets}.",
        "Better operational visibility and debugging",
        "low",
    ),
    "Security Signals": (
        "Audit dependencies and add version constraints",
        "Security concern at {targets}.",
        "Reduced vulnerability exposure",
        "low",
    ),
    "Technical Debt": (
        "Address accumulated technical debt",
        "Technical debt at {targets}.",
        "Reduced long-term maintenance cost",
        "varies",
    ),
}


def _generate_recommendation(finding: Finding) -> Recommendation:
    """Generate exactly one recommendation for a finding."""
    template = _RECOMMENDATION_TEMPLATES.get(
        finding.category,
        (
            f"Address finding in {finding.category}",
            f"Issue detected at {{targets}}.",
            "Improved code quality",
            "low",
        ),
    )
    recommendation_text, rationale_template, benefit, default_risk = template

    targets = ", ".join(c.component_name for c in finding.affected_components[:3])
    rationale = rationale_template.format(targets=targets)

    # Make recommendation text unique per finding by appending component context
    if targets:
        unique_text = f"{recommendation_text} in {targets} ({finding.finding_id})"
    else:
        unique_text = f"{recommendation_text} ({finding.finding_id})"

    priority = _compute_priority(
        impact=2.0 + (3.0 if finding.severity in ("high", "critical") else 1.0),
        confidence=finding.confidence,
        severity=finding.severity,
        scope=3.0 + (2.0 if len(finding.affected_components) > 3 else 0.0),
    )

    return Recommendation(
        finding_id=finding.finding_id,
        recommendation=unique_text,
        rationale=rationale,
        priority=priority,
        estimated_effort=_effort_from_priority(priority.score),
        estimated_risk=default_risk,
        expected_benefit=benefit,
    )


# ---------------------------------------------------------------------------
# Mission recommendation engine
# ---------------------------------------------------------------------------

_MISSION_TYPE_MAP: dict[str, str] = {
    "Architecture": "architecture_cleanup",
    "Coupling": "architecture_cleanup",
    "Complexity": "repository_maintenance",
    "Documentation": "documentation_refresh",
    "Testing": "testing_improvements",
    "Packaging": "packaging_improvements",
    "Configuration": "configuration_cleanup",
    "Dependencies": "dependency_review",
    "Security Signals": "dependency_review",
    "CLI": "documentation_refresh",
    "Public API": "documentation_refresh",
    "Performance": "repository_maintenance",
    "Maintainability": "repository_maintenance",
    "Observability": "repository_maintenance",
    "Technical Debt": "repository_maintenance",
}

_MISSION_TITLE_MAP: dict[str, str] = {
    "architecture_cleanup": "Architecture Cleanup",
    "documentation_refresh": "Documentation Refresh",
    "testing_improvements": "Testing Improvements",
    "dependency_review": "Dependency Review",
    "packaging_improvements": "Packaging Improvements",
    "configuration_cleanup": "Configuration Cleanup",
    "repository_maintenance": "Repository Maintenance",
    "release_readiness": "Release Readiness",
}


def _group_findings_into_missions(
    findings: tuple[Finding, ...],
    recommendations: tuple[Recommendation, ...],
) -> tuple[CandidateMission, ...]:
    """Group related findings into candidate missions."""
    if not findings:
        return ()

    # Group by mission type
    rec_by_finding = {r.finding_id: r for r in recommendations}
    groups: dict[str, list[Finding]] = {}
    for f in findings:
        mission_type = _MISSION_TYPE_MAP.get(f.category, "repository_maintenance")
        groups.setdefault(mission_type, []).append(f)

    missions: list[CandidateMission] = []
    mission_num = 0

    for mission_type, group_findings in sorted(groups.items()):
        mission_num += 1
        finding_ids = tuple(f.finding_id for f in group_findings)
        affected = tuple(
            sorted(set(
                c.component_path
                for f in group_findings
                for c in f.affected_components
            ))
        )

        # Compute mission-level priority from worst finding priority
        worst_priority = max(
            (rec_by_finding[f.finding_id].priority.score for f in group_findings if f.finding_id in rec_by_finding),
            default=5.0,
        )

        # Determine severity levels
        severities = {f.severity for f in group_findings}
        has_critical = "critical" in severities
        has_high = "high" in severities

        # Risk
        if has_critical:
            risk_level = "high"
            risk_reasoning = "Mission addresses critical findings"
        elif has_high:
            risk_level = "moderate"
            risk_reasoning = "Mission addresses high-severity findings"
        else:
            risk_level = "low"
            risk_reasoning = "Mission addresses low-to-medium findings"

        # Effort
        if len(group_findings) > 10 or worst_priority > 7:
            effort = "large"
        elif len(group_findings) > 5 or worst_priority > 5:
            effort = "medium"
        else:
            effort = "small"

        # Prerequisites
        prereqs: list[str] = []
        if mission_type == "release_readiness":
            # Release should come after testing and documentation
            if "testing_improvements" in groups:
                prereqs.append("testing_improvements")
            if "documentation_refresh" in groups:
                prereqs.append("documentation_refresh")

        title = _MISSION_TITLE_MAP.get(mission_type, mission_type.replace("_", " ").title())
        summary = f"Address {len(group_findings)} finding(s) in {', '.join(sorted(f.category for f in group_findings[:3]))}"

        priority = _compute_priority(
            impact=worst_priority * 0.8,
            confidence=0.8,
            severity="high" if has_critical else ("medium" if has_high else "low"),
            scope=min(10.0, len(group_findings) * 1.5),
        )

        missions.append(CandidateMission(
            mission_id=f"MISSION-{mission_num:03d}",
            title=f"{title} ({len(group_findings)} findings)",
            description=summary,
            objective=f"Resolve all {mission_type.replace('_', ' ')} findings in this repository",
            affected_modules=affected,
            estimated_effort=effort,
            priority=priority,
            risk=RiskAssessment(
                level=risk_level,
                reasoning=risk_reasoning,
                evidence=finding_ids,
                mitigation="Execute with full test suite validation",
            ),
            prerequisites=tuple(prereqs),
            supporting_findings=finding_ids,
            mission_type=mission_type,
        ))

    # If there are critical/high findings, add a release_readiness mission
    critical_findings = [f for f in findings if f.severity in ("critical", "high")]
    if critical_findings:
        mission_num += 1
        finding_ids = tuple(f.finding_id for f in critical_findings)
        priority = _compute_priority(
            impact=8.0,
            confidence=0.9,
            severity="high",
            scope=min(10.0, len(critical_findings) * 2.0),
        )
        missions.append(CandidateMission(
            mission_id=f"MISSION-{mission_num:03d}",
            title=f"Release Readiness ({len(critical_findings)} critical/high findings)",
            description=f"Address {len(critical_findings)} critical/high findings before release",
            objective="Ensure all critical and high findings are resolved before next release",
            affected_modules=tuple(sorted(set(
                c.component_path
                for f in critical_findings
                for c in f.affected_components
            ))),
            estimated_effort="large",
            priority=priority,
            risk=RiskAssessment(
                level="high",
                reasoning="Release blocked by critical/high findings",
                evidence=finding_ids,
                mitigation="Address all critical/high findings, run full regression, verify determinism",
            ),
            prerequisites=tuple(
                mt for mt in groups
                if mt in ("testing_improvements", "documentation_refresh")
            ),
            supporting_findings=finding_ids,
            mission_type="release_readiness",
        ))

    return tuple(sorted(missions, key=lambda m: (-m.priority.score, m.mission_id)))


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

def _assess_risk(findings: tuple[Finding, ...]) -> RiskAssessment:
    """Compute repository-level risk from findings."""
    if not findings:
        return RiskAssessment(
            level="low",
            reasoning="No findings detected",
            evidence=(),
            mitigation="No action required",
        )

    critical = sum(1 for f in findings if f.severity == "critical")
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    categories = {f.category for f in findings}

    if critical > 0:
        level = "critical"
        reasoning = f"{critical} critical findings require immediate attention"
    elif high > 3:
        level = "high"
        reasoning = f"{high} high-severity findings indicate significant risk"
    elif high > 0:
        level = "moderate"
        reasoning = f"{high} high and {medium} medium findings present moderate risk"
    elif medium > 5:
        level = "moderate"
        reasoning = f"{medium} medium findings across {len(categories)} categories"
    else:
        level = "low"
        reasoning = f"{medium} medium and {len(findings) - medium} low/info findings"

    evidence = tuple(f.finding_id for f in findings if f.severity in ("critical", "high"))

    if critical > 0:
        mitigation = "Address all critical findings before any release"
    elif high > 0:
        mitigation = "Plan resolution of high findings in next sprint"
    else:
        mitigation = "Address findings opportunistically during regular maintenance"

    return RiskAssessment(
        level=level,
        reasoning=reasoning,
        evidence=evidence,
        mitigation=mitigation,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _compute_summary(
    findings: tuple[Finding, ...],
    recommendations: tuple[Recommendation, ...],
    missions: tuple[CandidateMission, ...],
    risk: RiskAssessment,
) -> EngineeringSummary:
    """Compute executive summary."""
    critical = sum(1 for f in findings if f.severity == "critical")
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")
    info = sum(1 for f in findings if f.severity == "info")

    # Health score: starts at 100, deducts for findings with diminishing returns
    # Critical: -25 each (max -50), High: -8 each (max -40), Medium: -1.5 each (max -30), Low: -0.3 each (max -15), Info: 0
    critical_ded = min(50.0, critical * 25.0)
    high_ded = min(40.0, high * 8.0)
    medium_ded = min(30.0, medium * 1.5)
    low_ded = min(15.0, low * 0.3)
    health_score = max(0.0, 100.0 - critical_ded - high_ded - medium_ded - low_ded)

    risk_map = {"critical": "Critical", "high": "High", "moderate": "Moderate", "low": "Low"}

    return EngineeringSummary(
        total_findings=len(findings),
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        info_count=info,
        total_recommendations=len(recommendations),
        total_candidate_missions=len(missions),
        overall_risk=risk_map.get(risk.level, "Unknown"),
        health_score=round(health_score, 1),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_engineering(ri: dict[str, Any]) -> EngineeringIntelligence:
    """Analyze Repository Intelligence and produce Engineering Intelligence.

    This is the main entry point. It consumes a Repository Intelligence dict
    (parsed from REPOSITORY_INTELLIGENCE.json) and produces an
    EngineeringIntelligence model.

    Deterministic: same input → same output (byte-identical JSON).
    """
    repository = ri.get("repository", {})

    # Generate findings from all sources
    findings: list[Finding] = []
    findings.extend(_findings_from_cycles(ri))
    findings.extend(_findings_from_highly_connected(ri))
    findings.extend(_findings_from_complexity(ri))
    findings.extend(_findings_from_debt(ri))
    findings.extend(_findings_from_untested(ri))
    findings.extend(_findings_from_dependencies(ri))
    findings.extend(_findings_from_config(ri))
    findings.extend(_findings_from_cli(ri))
    findings.extend(_findings_from_public_api(ri))
    findings.extend(_findings_from_maintainability(ri))
    findings.extend(_findings_from_security(ri))

    # Sort findings deterministically: severity_desc, category, finding_id
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 5), f.category, f.finding_id))

    # Re-assign finding IDs deterministically
    findings = [
        Finding(
            finding_id=f"FINDING-{i + 1:03d}",
            category=f.category,
            severity=f.severity,
            confidence=f.confidence,
            title=f.title,
            explanation=f.explanation,
            evidence_references=f.evidence_references,
            affected_components=f.affected_components,
        )
        for i, f in enumerate(findings)
    ]

    findings_tuple = tuple(findings)

    # Generate recommendations
    recommendations = tuple(
        _generate_recommendation(f) for f in findings_tuple
    )

    # Generate candidate missions
    missions = _group_findings_into_missions(findings_tuple, recommendations)

    # Risk assessment
    risk = _assess_risk(findings_tuple)

    # Summary
    summary = _compute_summary(findings_tuple, recommendations, missions, risk)

    return EngineeringIntelligence(
        repository=repository,
        findings=findings_tuple,
        recommendations=recommendations,
        candidate_missions=missions,
        risk_assessment=risk,
        summary=summary,
    )
