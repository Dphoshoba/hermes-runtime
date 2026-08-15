"""Repository Intelligence — analysis engine.

Takes raw scan results and produces:
- Module graph (nodes, edges, cycles, isolated/highly-connected modules)
- Public API inventory
- Complexity signals
- Technical debt signals
- Architecture summary
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .repo_intel_models import (
    ArchitectureSummary,
    ClassInfo,
    CLIEntryPoint,
    ComplexitySignal,
    DebtSignal,
    FunctionInfo,
    ImportInfo,
    ModuleGraph,
    ModuleInfo,
    PublicAPI,
    RepositoryIntelligence,
)


def analyze_repository(scan: dict[str, Any]) -> RepositoryIntelligence:
    """Analyze scan results and produce complete intelligence model.

    Supports both Python-only (v1) and multi-language (v2) scan results.
    """
    repository = scan.get("repository", {})
    raw_modules = scan.get("modules", [])
    raw_tests = scan.get("tests", {})
    raw_deps = scan.get("dependencies", {})
    raw_config = scan.get("configuration", [])
    raw_cli = scan.get("cli_entry_points", [])
    schema_version = scan.get("schema_version", "1")

    # Multi-language fields (v2)
    repository_languages = scan.get("repository_languages", [])
    frameworks = scan.get("frameworks", [])
    source_files = scan.get("source_files", [])
    components = scan.get("components", [])
    hooks = scan.get("hooks", [])
    fetch_calls = scan.get("fetch_calls", [])
    routes = scan.get("routes", [])

    # Normalize module keys: support both 'path' and 'file_path'
    for m in raw_modules:
        if "path" not in m and "file_path" in m:
            m["path"] = m["file_path"]

    # Build module graph
    graph = _build_module_graph(raw_modules)

    # Build public API
    public_api = _build_public_api(raw_modules, raw_cli)

    # Build test intelligence
    from .repo_intel_models import TestIntelligence, TestModuleInfo

    test_modules_raw = raw_tests.get("test_modules", [])
    if not test_modules_raw and raw_tests.get("test_files"):
        # Convert test_files to test_modules format
        test_modules_raw = [
            {"path": tf, "name": Path(tf).stem, "imported_modules": [], "test_functions": [], "test_classes": [], "likely_targets": []}
            for tf in raw_tests["test_files"]
        ]

    test_modules = tuple(
        TestModuleInfo(
            path=t.get("path", ""),
            name=t.get("name", ""),
            imported_modules=tuple(t.get("imported_modules", ())),
            test_functions=tuple(t.get("test_functions", ())),
            test_classes=tuple(t.get("test_classes", ())),
            likely_targets=tuple(t.get("likely_targets", ())),
        )
        for t in test_modules_raw
    )
    tests = TestIntelligence(
        test_modules=test_modules,
        total_test_functions=raw_tests.get("total_test_functions", 0),
        total_test_classes=raw_tests.get("total_test_classes", 0),
        modules_with_tests=tuple(raw_tests.get("modules_with_tests", ())),
        modules_without_tests=tuple(raw_tests.get("modules_without_tests", ())),
    )

    # Build dependencies
    from .repo_intel_models import DependencyInfo, DependencyIntelligence

    deps_data = raw_deps
    if "production" in deps_data or "development" in deps_data:
        # JS-style deps - convert to Python-style for compatibility
        deps = DependencyIntelligence(
            runtime=tuple(DependencyInfo(name=n, category="runtime") for n in deps_data.get("production", [])),
            optional=(),
            test=(),
            dev=tuple(DependencyInfo(name=n, category="dev") for n in deps_data.get("development", [])),
            python_version=deps_data.get("python_version"),
            build_backend=deps_data.get("build_backend"),
        )
    else:
        deps = DependencyIntelligence(
            runtime=tuple(DependencyInfo(**d) for d in deps_data.get("runtime", [])),
            optional=tuple(DependencyInfo(**d) for d in deps_data.get("optional", [])),
            test=tuple(DependencyInfo(**d) for d in deps_data.get("test", [])),
            dev=tuple(DependencyInfo(**d) for d in deps_data.get("dev", [])),
            python_version=deps_data.get("python_version"),
            build_backend=deps_data.get("build_backend"),
        )

    # Build configuration
    from .repo_intel_models import ConfigurationFile
    configuration = tuple(ConfigurationFile(**c) for c in raw_config)

    # Build modules
    from .repo_intel_models import ModuleInfo
    modules = tuple(_raw_to_module(m) for m in raw_modules)

    # Complexity signals
    complexity = _detect_complexity(modules)

    # Debt signals
    debt = _detect_debt(modules, tests, deps, raw_cli, graph)

    # Merge scanner-provided signals
    scanner_complexity = scan.get("complexity_signals", [])
    scanner_debt = scan.get("debt_signals", [])

    # Convert scanner signals to model format
    all_complexity = list(complexity)
    for sc in scanner_complexity:
        all_complexity.append(ComplexitySignal(
            signal_type=sc.get("type", "unknown"),
            target=sc.get("file", ""),
            message=f"{sc.get('type', 'signal')}: {sc.get('value', '')}",
            severity=sc.get("severity", "low"),
        ))

    all_debt = list(debt)
    for sd in scanner_debt:
        all_debt.append(DebtSignal(
            signal_type=sd.get("type", "unknown"),
            target=sd.get("file", ""),
            message=sd.get("evidence", sd.get("type", "debt signal")),
            evidence=sd.get("evidence", ""),
            severity=sd.get("severity", "low"),
        ))

    # Architecture summary
    arch = _build_architecture_summary(repository, modules, tests, deps, raw_cli, all_complexity, all_debt)

    # Create RI with extended fields
    ri = RepositoryIntelligence(
        repository=repository,
        modules=modules,
        public_api=public_api,
        module_graph=graph,
        tests=tests,
        dependencies=deps,
        configuration=configuration,
        complexity_signals=tuple(all_complexity),
        technical_debt_signals=tuple(all_debt),
        architecture_summary=arch,
    )

    # Add multi-language fields as metadata
    ri_dict = ri.as_dict()
    ri_dict["repository_languages"] = repository_languages
    ri_dict["frameworks"] = frameworks
    ri_dict["source_files"] = source_files
    ri_dict["components"] = components
    ri_dict["hooks"] = hooks
    ri_dict["fetch_calls"] = fetch_calls
    ri_dict["routes"] = routes

    # Reconstruct RI with extended dict
    ri_dict["schema_version"] = scan.get("schema_version", "1")
    return ri


def _raw_to_module(raw: dict[str, Any]) -> ModuleInfo:
    """Convert raw module dict to ModuleInfo."""
    from .repo_intel_models import ClassInfo, FunctionInfo, ImportInfo

    imports = tuple(
        ImportInfo(
            module=i.get("module") or i.get("source", ""),
            names=tuple(i.get("names", ())),
            level=i.get("level", 0),
            is_from_import=i.get("is_from_import", False),
        )
        for i in raw.get("imports", [])
    )

    classes = tuple(
        ClassInfo(
            name=c["name"],
            bases=tuple(c.get("bases", ())),
            decorators=tuple(c.get("decorators", ())),
            methods=tuple(
                FunctionInfo(
                    name=m["name"],
                    signature=m.get("signature", "()"),
                    is_public=m.get("is_public", True),
                    is_async=m.get("is_async", False),
                    is_method=m.get("is_method", False),
                    decorators=tuple(m.get("decorators", ())),
                    docstring=m.get("docstring"),
                    line_count=m.get("line_count", 0),
                    ast_size=m.get("ast_size", 0),
                    nested_depth=m.get("nested_depth", 0),
                )
                for m in c.get("methods", [])
            ),
            docstring=c.get("docstring"),
            line_count=c.get("line_count", 0),
            ast_size=c.get("ast_size", 0),
        )
        for c in raw.get("classes", [])
    )

    functions = tuple(
        FunctionInfo(
            name=f["name"],
            signature=f.get("signature", "()"),
            is_public=f.get("is_public", True),
            is_async=f.get("is_async", False),
            is_method=f.get("is_method", False),
            decorators=tuple(f.get("decorators", ())),
            docstring=f.get("docstring"),
            line_count=f.get("line_count", 0),
            ast_size=f.get("ast_size", 0),
            nested_depth=f.get("nested_depth", 0),
        )
        for f in raw.get("functions", [])
    )

    return ModuleInfo(
        path=raw["path"],
        package=raw.get("package"),
        name=raw.get("name"),
        imports=imports,
        classes=classes,
        functions=functions,
        module_constants=tuple(raw.get("module_constants", ())),
        line_count=raw.get("line_count", 0),
        ast_size=raw.get("ast_size", 0),
        has_docstring=raw.get("has_docstring", False),
    )


def _build_module_graph(raw_modules: list[dict[str, Any]]) -> ModuleGraph:
    """Build directed graph of module imports."""
    # Collect all module paths
    all_paths = {m["path"] for m in raw_modules}
    # Map module names to paths
    name_to_path: dict[str, str] = {}
    for m in raw_modules:
        path = m["path"]
        # Strip .py suffix and convert / to .
        if path.endswith(".py"):
            stem = path[:-3].replace("/", ".").replace("\\", ".")
            name_to_path[stem] = path
            # Also map the simple name
            simple = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].replace(".py", "")
            if simple not in name_to_path:
                name_to_path[simple] = path

    edges: list[tuple[str, str]] = []
    for m in raw_modules:
        src = m["path"]
        for imp in m.get("imports", []):
            # Support both Python ('module') and JS/TS ('source') import keys
            mod_name = imp.get("module") or imp.get("source", "")
            if not mod_name:
                continue
            # Try to resolve to a local module
            target = _resolve_module(mod_name, name_to_path, all_paths)
            if target and target != src:
                edges.append((src, target))

    nodes = sorted(all_paths)
    edges_deduped = sorted(set(edges))

    # Find isolated modules (no edges)
    connected = set()
    for src, tgt in edges_deduped:
        connected.add(src)
        connected.add(tgt)
    isolated = tuple(sorted(all_paths - connected))

    # Find highly connected modules (in-degree + out-degree > 5)
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for src, tgt in edges_deduped:
        out_degree[src] += 1
        in_degree[tgt] += 1
    highly_connected = tuple(
        sorted(
            {n for n in all_paths if in_degree[n] + out_degree[n] > 5},
        )
    )

    # Detect import cycles (DFS)
    cycles = _detect_cycles(nodes, edges_deduped)

    return ModuleGraph(
        nodes=tuple(nodes),
        edges=tuple(edges_deduped),
        isolated_modules=isolated,
        highly_connected_modules=highly_connected,
        import_cycles=tuple(cycles),
    )


def _resolve_module(
    mod_name: str,
    name_to_path: dict[str, str],
    all_paths: set[str],
) -> str | None:
    """Try to resolve a module name to a local file path."""
    # Direct match
    if mod_name in name_to_path:
        return name_to_path[mod_name]

    # Try as package/__init__.py
    init_path = mod_name.replace(".", "/") + "/__init__.py"
    if init_path in all_paths:
        return init_path

    # Try as module.py
    py_path = mod_name.replace(".", "/") + ".py"
    if py_path in all_paths:
        return py_path

    # Try partial match (last component)
    parts = mod_name.split(".")
    for i in range(len(parts)):
        partial = ".".join(parts[i:])
        if partial in name_to_path:
            return name_to_path[partial]

    return None


def _detect_cycles(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Detect cycles in directed graph using DFS."""
    graph: dict[str, list[str]] = defaultdict(list)
    for src, tgt in edges:
        graph[src].append(tgt)

    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            # Found cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return
        visiting.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor in nodes:
                dfs(neighbor, path)
        path.pop()
        visiting.discard(node)
        visited.add(node)

    for node in nodes:
        if node not in visited:
            dfs(node, [])

    return sorted(cycles, key=lambda c: c[0])


def _build_public_api(
    raw_modules: list[dict[str, Any]],
    raw_cli: list[dict[str, Any]],
) -> PublicAPI:
    """Build public API inventory from scan results."""
    from .repo_intel_models import ClassInfo, CLIEntryPoint, FunctionInfo

    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    constants: list[tuple[str, str]] = []

    for m in raw_modules:
        mod_path = m["path"]

        for c in m.get("classes", []):
            classes.append(ClassInfo(
                name=c["name"],
                bases=tuple(c.get("bases", ())),
                decorators=tuple(c.get("decorators", ())),
                methods=tuple(),  # Methods are nested in class
                docstring=c.get("docstring"),
                line_count=c.get("line_count", 0),
            ))

        for f in m.get("functions", []):
            if f.get("is_public", True):
                functions.append(FunctionInfo(
                    name=f["name"],
                    signature=f.get("signature", "()"),
                    is_public=True,
                    is_async=f.get("is_async", False),
                    decorators=tuple(f.get("decorators", ())),
                    docstring=f.get("docstring"),
                    line_count=f.get("line_count", 0),
                ))

        for const in m.get("module_constants", []):
            constants.append((mod_path, const))

    cli_points = tuple(
        CLIEntryPoint(name=e["name"], target=e["target"])
        for e in raw_cli
    )

    return PublicAPI(
        classes=tuple(sorted(classes, key=lambda c: c.name)),
        functions=tuple(sorted(functions, key=lambda f: f.name)),
        module_constants=tuple(sorted(constants)),
        cli_entry_points=cli_points,
    )


def _detect_complexity(modules: tuple) -> list[ComplexitySignal]:
    """Detect complexity signals."""
    signals: list[ComplexitySignal] = []

    for mod in modules:
        path = mod.path

        # Large module
        if mod.line_count > 500:
            signals.append(ComplexitySignal(
                signal_type="large_module",
                target=path,
                message=f"Module has {mod.line_count} lines",
                severity="warning" if mod.line_count > 1000 else "info",
            ))

        # Many imports
        if len(mod.imports) > 15:
            signals.append(ComplexitySignal(
                signal_type="many_imports",
                target=path,
                message=f"Module has {len(mod.imports)} imports",
                severity="warning",
            ))

        # Complex functions
        for func in mod.functions:
            if func.ast_size > 200:
                signals.append(ComplexitySignal(
                    signal_type="complex_function",
                    target=f"{path}::{func.name}",
                    message=f"Function has AST size {func.ast_size}",
                    severity="warning",
                ))
            if func.nested_depth > 3:
                signals.append(ComplexitySignal(
                    signal_type="deep_nesting",
                    target=f"{path}::{func.name}",
                    message=f"Function has nesting depth {func.nested_depth}",
                    severity="warning",
                ))

        # Large classes
        for cls in mod.classes:
            if cls.line_count > 200:
                signals.append(ComplexitySignal(
                    signal_type="large_class",
                    target=f"{path}::{cls.name}",
                    message=f"Class has {cls.line_count} lines",
                    severity="warning",
                ))
            if len(cls.methods) > 15:
                signals.append(ComplexitySignal(
                    signal_type="many_methods",
                    target=f"{path}::{cls.name}",
                    message=f"Class has {len(cls.methods)} methods",
                    severity="warning",
                ))

    return sorted(signals, key=lambda s: (s.severity, s.target))


def _detect_debt(
    modules: tuple,
    tests,
    deps,
    raw_cli: list[dict[str, Any]],
    graph: ModuleGraph,
) -> list[DebtSignal]:
    """Detect technical debt signals backed by evidence."""
    signals: list[DebtSignal] = []
    all_paths = {m.path for m in modules}

    # Modules without docstrings
    for mod in modules:
        if not mod.has_docstring and mod.line_count > 20:
            signals.append(DebtSignal(
                signal_type="missing_docstring",
                target=mod.path,
                message="Module lacks docstring",
                evidence=f"Module has {mod.line_count} lines but no module docstring",
            ))

    # Public functions without docstrings
    for mod in modules:
        for func in mod.functions:
            if func.is_public and not func.docstring and func.line_count > 5:
                signals.append(DebtSignal(
                    signal_type="missing_function_docstring",
                    target=f"{mod.path}::{func.name}",
                    message="Public function lacks docstring",
                    evidence=f"Public function {func.name}() has {func.line_count} lines but no docstring",
                ))

    # Modules without tests
    for mod_path in tests.modules_without_tests:
        if mod_path in all_paths:
            signals.append(DebtSignal(
                signal_type="no_tests",
                target=mod_path,
                message="Module has no test coverage",
                evidence=f"Module {mod_path} not referenced by any test module",
            ))

    # Import cycles
    for cycle in graph.import_cycles:
        signals.append(DebtSignal(
            signal_type="import_cycle",
            target=" → ".join(cycle),
            message=f"Import cycle detected ({len(cycle)} modules)",
            evidence=f"Cycle: {' → '.join(cycle)}",
            severity="warning",
        ))

    # Isolated modules
    for isolated in graph.isolated_modules:
        signals.append(DebtSignal(
            signal_type="isolated_module",
            target=isolated,
            message="Module has no imports from or to other project modules",
            evidence=f"Module {isolated} is disconnected from the project graph",
        ))

    return sorted(signals, key=lambda s: (s.severity, s.signal_type, s.target))


def _build_architecture_summary(
    repository: dict[str, Any],
    modules: tuple,
    tests,
    deps,
    raw_cli: list[dict[str, Any]],
    complexity: list[ComplexitySignal],
    debt: list[DebtSignal],
) -> ArchitectureSummary:
    """Generate high-level architecture summary."""
    packages: set[str] = set()
    for mod in modules:
        if mod.package:
            # Get top-level package
            top = mod.package.split("/")[0].split("\\")[0]
            packages.add(top)

    total_classes = sum(len(m.classes) for m in modules)
    total_functions = sum(len(m.functions) for m in modules)

    return ArchitectureSummary(
        repository_name=repository.get("name", "unknown"),
        description=repository.get("description"),
        packages=tuple(sorted(packages)),
        module_count=len(modules),
        class_count=total_classes,
        function_count=total_functions,
        test_module_count=len(tests.test_modules),
        cli_entry_point_count=len(raw_cli),
        dependency_count=len(deps.runtime) + len(deps.optional) + len(deps.test) + len(deps.dev),
        complexity_signal_count=len(complexity),
        debt_signal_count=len(debt),
    )
