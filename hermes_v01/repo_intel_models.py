"""Repository Intelligence — data models for repository analysis.

Models only what is actually observed via static inspection.
No inference, no guessing, no module importing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImportInfo:
    """A single import statement observed in source."""
    module: str
    names: tuple[str, ...] = ()
    level: int = 0  # relative import depth (0 = absolute)
    is_from_import: bool = False

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"module": self.module}
        if self.names:
            data["names"] = list(self.names)
        if self.level:
            data["level"] = self.level
        if self.is_from_import:
            data["is_from_import"] = True
        return data


@dataclass(frozen=True)
class FunctionInfo:
    """A function or method observed via AST."""
    name: str
    signature: str
    is_public: bool = True
    is_async: bool = False
    is_method: bool = False
    decorators: tuple[str, ...] = ()
    docstring: str | None = None
    line_count: int = 0
    ast_size: int = 0
    nested_depth: int = 0

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "signature": self.signature,
            "is_public": self.is_public,
        }
        if self.is_async:
            data["is_async"] = True
        if self.is_method:
            data["is_method"] = True
        if self.decorators:
            data["decorators"] = list(self.decorators)
        if self.docstring:
            data["docstring"] = self.docstring
        if self.line_count:
            data["line_count"] = self.line_count
        if self.ast_size:
            data["ast_size"] = self.ast_size
        if self.nested_depth:
            data["nested_depth"] = self.nested_depth
        return data


@dataclass(frozen=True)
class ClassInfo:
    """A class observed via AST."""
    name: str
    bases: tuple[str, ...] = ()
    decorators: tuple[str, ...] = ()
    methods: tuple[FunctionInfo, ...] = ()
    docstring: str | None = None
    line_count: int = 0
    ast_size: int = 0

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name}
        if self.bases:
            data["bases"] = list(self.bases)
        if self.decorators:
            data["decorators"] = list(self.decorators)
        if self.methods:
            data["methods"] = [m.as_dict() for m in self.methods]
        if self.docstring:
            data["docstring"] = self.docstring
        if self.line_count:
            data["line_count"] = self.line_count
        if self.ast_size:
            data["ast_size"] = self.ast_size
        return data


@dataclass(frozen=True)
class ModuleInfo:
    """A Python module observed via AST and filesystem."""
    path: str
    package: str | None = None
    name: str | None = None
    imports: tuple[ImportInfo, ...] = ()
    classes: tuple[ClassInfo, ...] = ()
    functions: tuple[FunctionInfo, ...] = ()
    module_constants: tuple[str, ...] = ()
    line_count: int = 0
    ast_size: int = 0
    has_docstring: bool = False

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"path": self.path}
        if self.package:
            data["package"] = self.package
        if self.name:
            data["name"] = self.name
        if self.imports:
            data["imports"] = [i.as_dict() for i in self.imports]
        if self.classes:
            data["classes"] = [c.as_dict() for c in self.classes]
        if self.functions:
            data["functions"] = [f.as_dict() for f in self.functions]
        if self.module_constants:
            data["module_constants"] = list(self.module_constants)
        if self.line_count:
            data["line_count"] = self.line_count
        if self.ast_size:
            data["ast_size"] = self.ast_size
        if self.has_docstring:
            data["has_docstring"] = True
        return data


@dataclass(frozen=True)
class DependencyInfo:
    """A declared project dependency."""
    name: str
    version_spec: str | None = None
    category: str = "runtime"  # runtime | optional | test | dev

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "category": self.category}
        if self.version_spec:
            data["version_spec"] = self.version_spec
        return data


@dataclass(frozen=True)
class TestModuleInfo:
    """A test module and its relationship to implementation modules."""
    path: str
    name: str
    imported_modules: tuple[str, ...] = ()
    test_functions: tuple[str, ...] = ()
    test_classes: tuple[str, ...] = ()
    likely_targets: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": self.path,
            "name": self.name,
        }
        if self.imported_modules:
            data["imported_modules"] = list(self.imported_modules)
        if self.test_functions:
            data["test_functions"] = list(self.test_functions)
        if self.test_classes:
            data["test_classes"] = list(self.test_classes)
        if self.likely_targets:
            data["likely_targets"] = list(self.likely_targets)
        return data


@dataclass(frozen=True)
class CLIEntryPoint:
    """A console-script entry point."""
    name: str
    target: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "target": self.target}


@dataclass(frozen=True)
class ConfigurationFile:
    """A configuration file discovered in the repository."""
    path: str
    kind: str  # pyproject.toml, setup.cfg, .gitignore, etc.

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind}


@dataclass(frozen=True)
class ComplexitySignal:
    """A static complexity signal observed in the codebase."""
    signal_type: str
    target: str
    message: str
    severity: str = "info"  # info | warning

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "target": self.target,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class DebtSignal:
    """A technical debt signal backed by observed evidence."""
    signal_type: str
    target: str
    message: str
    evidence: str
    severity: str = "info"

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "target": self.target,
            "message": self.message,
            "evidence": self.evidence,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class ModuleGraph:
    """Directed graph of module imports."""
    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    isolated_modules: tuple[str, ...] = ()
    highly_connected_modules: tuple[str, ...] = ()
    import_cycles: tuple[tuple[str, ...], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "nodes": list(self.nodes),
            "edges": [{"from": e[0], "to": e[1]} for e in self.edges],
        }
        if self.isolated_modules:
            data["isolated_modules"] = list(self.isolated_modules)
        if self.highly_connected_modules:
            data["highly_connected_modules"] = list(self.highly_connected_modules)
        if self.import_cycles:
            data["import_cycles"] = [list(c) for c in self.import_cycles]
        return data


@dataclass(frozen=True)
class PublicAPI:
    """Inventory of public API surface."""
    classes: tuple[ClassInfo, ...] = ()
    functions: tuple[FunctionInfo, ...] = ()
    module_constants: tuple[tuple[str, str], ...] = ()  # (module, constant_name)
    cli_entry_points: tuple[CLIEntryPoint, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.classes:
            data["classes"] = [c.as_dict() for c in self.classes]
        if self.functions:
            data["functions"] = [f.as_dict() for f in self.functions]
        if self.module_constants:
            data["module_constants"] = [{"module": m, "name": n} for m, n in self.module_constants]
        if self.cli_entry_points:
            data["cli_entry_points"] = [e.as_dict() for e in self.cli_entry_points]
        return data


@dataclass(frozen=True)
class TestIntelligence:
    """Test analysis results."""
    test_modules: tuple[TestModuleInfo, ...] = ()
    total_test_functions: int = 0
    total_test_classes: int = 0
    modules_with_tests: tuple[str, ...] = ()
    modules_without_tests: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "total_test_functions": self.total_test_functions,
            "total_test_classes": self.total_test_classes,
        }
        if self.test_modules:
            data["test_modules"] = [t.as_dict() for t in self.test_modules]
        if self.modules_with_tests:
            data["modules_with_tests"] = list(self.modules_with_tests)
        if self.modules_without_tests:
            data["modules_without_tests"] = list(self.modules_without_tests)
        return data


@dataclass(frozen=True)
class DependencyIntelligence:
    """Dependency analysis results."""
    runtime: tuple[DependencyInfo, ...] = ()
    optional: tuple[DependencyInfo, ...] = ()
    test: tuple[DependencyInfo, ...] = ()
    dev: tuple[DependencyInfo, ...] = ()
    python_version: str | None = None
    build_backend: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.runtime:
            data["runtime"] = [d.as_dict() for d in self.runtime]
        if self.optional:
            data["optional"] = [d.as_dict() for d in self.optional]
        if self.test:
            data["test"] = [d.as_dict() for d in self.test]
        if self.dev:
            data["dev"] = [d.as_dict() for d in self.dev]
        if self.python_version:
            data["python_version"] = self.python_version
        if self.build_backend:
            data["build_backend"] = self.build_backend
        return data


@dataclass(frozen=True)
class ArchitectureSummary:
    """High-level architecture model."""
    repository_name: str
    description: str | None = None
    packages: tuple[str, ...] = ()
    module_count: int = 0
    class_count: int = 0
    function_count: int = 0
    test_module_count: int = 0
    cli_entry_point_count: int = 0
    dependency_count: int = 0
    complexity_signal_count: int = 0
    debt_signal_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "repository_name": self.repository_name,
            "module_count": self.module_count,
            "class_count": self.class_count,
            "function_count": self.function_count,
            "test_module_count": self.test_module_count,
            "cli_entry_point_count": self.cli_entry_point_count,
            "dependency_count": self.dependency_count,
            "complexity_signal_count": self.complexity_signal_count,
            "debt_signal_count": self.debt_signal_count,
        }
        if self.description:
            data["description"] = self.description
        if self.packages:
            data["packages"] = list(self.packages)
        return data


@dataclass(frozen=True)
class RepositoryIntelligence:
    """Complete repository intelligence model."""
    schema_version: str = "1"
    repository: dict[str, Any] = field(default_factory=dict)
    modules: tuple[ModuleInfo, ...] = ()
    public_api: PublicAPI = field(default_factory=PublicAPI)
    module_graph: ModuleGraph = field(default_factory=ModuleGraph)
    tests: TestIntelligence = field(default_factory=TestIntelligence)
    dependencies: DependencyIntelligence = field(default_factory=DependencyIntelligence)
    configuration: tuple[ConfigurationFile, ...] = ()
    complexity_signals: tuple[ComplexitySignal, ...] = ()
    technical_debt_signals: tuple[DebtSignal, ...] = ()
    architecture_summary: ArchitectureSummary | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "repository": dict(self.repository),
        }
        if self.modules:
            data["modules"] = [m.as_dict() for m in self.modules]
        if self.public_api:
            data["public_api"] = self.public_api.as_dict()
        if self.module_graph:
            data["module_graph"] = self.module_graph.as_dict()
        if self.tests:
            data["tests"] = self.tests.as_dict()
        if self.dependencies:
            data["dependencies"] = self.dependencies.as_dict()
        if self.configuration:
            data["configuration"] = [c.as_dict() for c in self.configuration]
        if self.complexity_signals:
            data["complexity_signals"] = [s.as_dict() for s in self.complexity_signals]
        if self.technical_debt_signals:
            data["technical_debt_signals"] = [s.as_dict() for s in self.technical_debt_signals]
        if self.architecture_summary:
            data["architecture_summary"] = self.architecture_summary.as_dict()
        return data
