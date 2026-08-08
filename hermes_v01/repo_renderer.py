"""Repository Intelligence — artifact renderer.

Renders RepositoryIntelligence to JSON and Markdown.
The JSON artifact is authoritative; Markdown is derived from the same model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .repo_intel_models import RepositoryIntelligence


def render_json(intelligence: RepositoryIntelligence, indent: int = 2) -> str:
    """Render deterministic JSON from intelligence model."""
    return json.dumps(
        intelligence.as_dict(),
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
    )


def render_markdown(intelligence: RepositoryIntelligence) -> str:
    """Render human-readable Markdown from intelligence model."""
    lines: list[str] = []
    repo = intelligence.repository
    arch = intelligence.architecture_summary

    lines.append(f"# Repository Intelligence — {repo.get('name', 'Unknown')}")
    lines.append("")
    if repo.get("description"):
        lines.append(f"**Description:** {repo['description']}")
        lines.append("")
    if repo.get("git_revision"):
        lines.append(f"**Git revision:** `{repo['git_revision']}`")
        lines.append("")

    # Architecture summary
    if arch:
        lines.append("## Architecture Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Modules | {arch.module_count} |")
        lines.append(f"| Classes | {arch.class_count} |")
        lines.append(f"| Functions | {arch.function_count} |")
        lines.append(f"| Test modules | {arch.test_module_count} |")
        lines.append(f"| CLI entry points | {arch.cli_entry_point_count} |")
        lines.append(f"| Dependencies | {arch.dependency_count} |")
        lines.append(f"| Complexity signals | {arch.complexity_signal_count} |")
        lines.append(f"| Debt signals | {arch.debt_signal_count} |")
        if arch.packages:
            lines.append(f"| Packages | {', '.join(arch.packages)} |")
        lines.append("")

    # Public API
    api = intelligence.public_api
    if api.classes or api.functions or api.cli_entry_points:
        lines.append("## Public API")
        lines.append("")
        if api.classes:
            lines.append(f"### Classes ({len(api.classes)})")
            lines.append("")
            for cls in api.classes:
                bases = f"({', '.join(cls.bases)})" if cls.bases else ""
                lines.append(f"- **{cls.name}**{bases}")
                for method in cls.methods:
                    if method.is_public:
                        lines.append(f"  - `{method.name}{method.signature}`")
            lines.append("")
        if api.functions:
            lines.append(f"### Functions ({len(api.functions)})")
            lines.append("")
            for func in api.functions:
                async_prefix = "async " if func.is_async else ""
                lines.append(f"- `{async_prefix}{func.name}{func.signature}`")
            lines.append("")
        if api.cli_entry_points:
            lines.append(f"### CLI Entry Points ({len(api.cli_entry_points)})")
            lines.append("")
            for ep in api.cli_entry_points:
                lines.append(f"- `{ep.name}` → `{ep.target}`")
            lines.append("")

    # Module graph
    graph = intelligence.module_graph
    if graph.nodes:
        lines.append("## Module Graph")
        lines.append("")
        lines.append(f"- **Nodes:** {len(graph.nodes)}")
        lines.append(f"- **Edges:** {len(graph.edges)}")
        if graph.isolated_modules:
            lines.append(f"- **Isolated modules:** {len(graph.isolated_modules)}")
            for m in graph.isolated_modules:
                lines.append(f"  - `{m}`")
        if graph.highly_connected_modules:
            lines.append(f"- **Highly connected modules:** {len(graph.highly_connected_modules)}")
            for m in graph.highly_connected_modules:
                lines.append(f"  - `{m}`")
        if graph.import_cycles:
            lines.append(f"- **Import cycles:** {len(graph.import_cycles)}")
            for cycle in graph.import_cycles:
                lines.append(f"  - `{' → '.join(cycle)}`")
        lines.append("")

    # Tests
    tests = intelligence.tests
    if tests.test_modules:
        lines.append("## Test Intelligence")
        lines.append("")
        lines.append(f"- **Test modules:** {len(tests.test_modules)}")
        lines.append(f"- **Test functions:** {tests.total_test_functions}")
        lines.append(f"- **Test classes:** {tests.total_test_classes}")
        lines.append(f"- **Modules with tests:** {len(tests.modules_with_tests)}")
        lines.append(f"- **Modules without tests:** {len(tests.modules_without_tests)}")
        lines.append("")

    # Dependencies
    deps = intelligence.dependencies
    if deps.runtime or deps.optional or deps.test:
        lines.append("## Dependencies")
        lines.append("")
        if deps.python_version:
            lines.append(f"- **Python requirement:** {deps.python_version}")
        if deps.build_backend:
            lines.append(f"- **Build backend:** {deps.build_backend}")
        if deps.runtime:
            lines.append(f"- **Runtime:** {len(deps.runtime)}")
            for d in deps.runtime:
                ver = f" `{d.version_spec}`" if d.version_spec else ""
                lines.append(f"  - {d.name}{ver}")
        if deps.optional:
            lines.append(f"- **Optional:** {len(deps.optional)}")
            for d in deps.optional:
                ver = f" `{d.version_spec}`" if d.version_spec else ""
                lines.append(f"  - {d.name}{ver}")
        if deps.test:
            lines.append(f"- **Test:** {len(deps.test)}")
            for d in deps.test:
                ver = f" `{d.version_spec}`" if d.version_spec else ""
                lines.append(f"  - {d.name}{ver}")
        lines.append("")

    # Complexity signals
    if intelligence.complexity_signals:
        lines.append("## Complexity Signals")
        lines.append("")
        for sig in intelligence.complexity_signals:
            lines.append(f"- **[{sig.severity}]** `{sig.target}`: {sig.message}")
        lines.append("")

    # Technical debt
    if intelligence.technical_debt_signals:
        lines.append("## Technical Debt Signals")
        lines.append("")
        for sig in intelligence.technical_debt_signals:
            lines.append(f"- **[{sig.severity}]** `{sig.target}`: {sig.message}")
            lines.append(f"  - Evidence: {sig.evidence}")
        lines.append("")

    return "\n".join(lines)


def save_artifacts(
    intelligence: RepositoryIntelligence,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Save JSON and Markdown artifacts atomically."""
    from .utils import atomic_write_json

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "REPOSITORY_INTELLIGENCE.json"
    md_path = output_dir / "REPOSITORY_INTELLIGENCE.md"

    # JSON (authoritative)
    atomic_write_json(json_path, intelligence.as_dict())

    # Markdown (derived from same model)
    md_content = render_markdown(intelligence)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
