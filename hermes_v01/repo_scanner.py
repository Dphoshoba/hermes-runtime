"""Repository Intelligence — static scanner.

Inspects a repository using filesystem traversal and AST parsing.
Does not import or execute target repository code.
"""

from __future__ import annotations

import ast
import os
import re
import textwrap
from pathlib import Path
from typing import Any

from .repo_intel_models import (
    ClassInfo,
    CLIEntryPoint,
    ConfigurationFile,
    DependencyInfo,
    DependencyIntelligence,
    FunctionInfo,
    ImportInfo,
    ModuleGraph,
    ModuleInfo,
    PublicAPI,
    TestIntelligence,
    TestModuleInfo,
)

from .scanner_registry import COMMON_CONFIG_NAMES

# Python-specific configuration files (superset of COMMON_CONFIG_NAMES)
_CONFIG_NAMES = COMMON_CONFIG_NAMES | {
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini",
    ".flake8",
    "pytest.ini", "conftest.py", ".pre-commit-config.yaml",
    "mypy.ini", ".mypy.ini", "ruff.toml", ".ruff.toml",
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "Pipfile", "poetry.lock", "uv.lock",
}


def scan_repository(repo_root: Path) -> dict[str, Any]:
    """Top-level scanner entry point. Returns raw scan results.

    Supports multi-language scanning via the scanner registry.
    Falls back to Python-only scanning if registry unavailable.
    """
    try:
        from .scanner_registry import get_registry
        registry = get_registry()
        detections = registry.detect(repo_root)
        detected = [d for d in detections if d.get("detected", False)]

        if detected:
            # Use registry for multi-language scanning
            result = registry.scan(repo_root)
            repo_info = _scan_repository_metadata(repo_root)
            repo_info["file_count"] = result.get("_total_files", 0)
            result["repository"] = repo_info
            result["schema_version"] = "2"
            return result
    except ImportError:
        pass

    # Fallback: Python-only scanning
    repo_info = _scan_repository_metadata(repo_root)
    py_files = _discover_python_files(repo_root)
    modules = _scan_modules(repo_root, py_files)
    tests = _scan_tests(repo_root, py_files, modules)
    deps = _scan_dependencies(repo_root)
    config = _scan_configuration(repo_root)
    cli_entries = _scan_cli_entry_points(repo_root)

    return {
        "repository": {**repo_info, "file_count": len(py_files)},
        "repository_languages": ["python"],
        "frameworks": [],
        "modules": modules,
        "tests": tests,
        "dependencies": deps,
        "configuration": config,
        "cli_entry_points": cli_entries,
        "schema_version": "1",
    }


def _scan_repository_metadata(repo_root: Path) -> dict[str, Any]:
    """Extract basic repository metadata."""
    name = repo_root.name
    description = None
    git_revision = None

    # Try pyproject.toml for description
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("description"):
                    match = re.search(r'description\s*=\s*["\'](.+?)["\']', line)
                    if match:
                        description = match.group(1)
                        break
        except Exception:
            pass

    # Try git for revision
    git_head = repo_root / ".git" / "HEAD"
    if git_head.exists():
        try:
            head_content = git_head.read_text(encoding="utf-8").strip()
            if head_content.startswith("ref: "):
                ref = head_content[5:]
                ref_path = repo_root / ".git" / ref
                if ref_path.exists():
                    git_revision = ref_path.read_text(encoding="utf-8").strip()[:12]
            else:
                git_revision = head_content[:12]
        except Exception:
            pass

    result: dict[str, Any] = {"name": name, "path": str(repo_root)}
    if description:
        result["description"] = description
    if git_revision:
        result["git_revision"] = git_revision
    return result


def _discover_python_files(repo_root: Path) -> list[Path]:
    """Discover all Python files in the repository."""
    py_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip hidden dirs, __pycache__, .git, node_modules, .tox, .eggs, validation
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ("__pycache__", "node_modules", ".tox", ".eggs", ".nox", "venv", ".venv", "validation")
        ]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(Path(dirpath) / fname)
    return sorted(py_files)


def _scan_modules(repo_root: Path, py_files: list[Path]) -> list[dict[str, Any]]:
    """Scan all Python modules via AST parsing."""
    modules: list[dict[str, Any]] = []
    for py_file in py_files:
        try:
            module = _parse_module(repo_root, py_file)
            modules.append(module)
        except Exception:
            # Malformed Python — record what we can
            rel = py_file.relative_to(repo_root) if py_file.is_relative_to(repo_root) else py_file
            modules.append({
                "path": str(rel),
                "parse_error": True,
                "line_count": _count_lines(py_file),
            })
    return modules


def _parse_module(repo_root: Path, py_file: Path) -> dict[str, Any]:
    """Parse a single Python module via AST."""
    rel = py_file.relative_to(repo_root) if py_file.is_relative_to(repo_root) else py_file
    content = py_file.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    line_count = len(lines)

    try:
        tree = ast.parse(content, filename=str(py_file))
    except SyntaxError:
        return {
            "path": str(rel),
            "parse_error": True,
            "line_count": line_count,
        }

    ast_size = _count_ast_nodes(tree)
    imports = _extract_imports(tree)
    classes = _extract_classes(tree)
    functions = _extract_functions(tree, is_method=False)
    constants = _extract_constants(tree)
    has_docstring = bool(ast.get_docstring(tree))

    # Determine package
    parts = rel.parts
    package = None
    if len(parts) > 1:
        package = str(Path(*parts[:-1])) if len(parts) > 1 else None

    module_name = rel.stem if rel.suffix == ".py" else str(rel)

    result: dict[str, Any] = {
        "path": str(rel),
        "line_count": line_count,
        "ast_size": ast_size,
        "has_docstring": has_docstring,
    }
    if package:
        result["package"] = package
    if module_name:
        result["name"] = module_name
    if imports:
        result["imports"] = imports
    if classes:
        result["classes"] = classes
    if functions:
        result["functions"] = functions
    if constants:
        result["module_constants"] = constants
    return result


def _extract_imports(tree: ast.Module) -> list[dict[str, Any]]:
    """Extract all import statements from AST."""
    imports: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                entry: dict[str, Any] = {"module": alias.name}
                if alias.asname:
                    entry["asname"] = alias.asname
                imports.append(entry)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            entry = {"module": node.module}
            if node.level:
                entry["level"] = node.level
            if node.names:
                entry["names"] = [a.name for a in node.names]
                entry["is_from_import"] = True
            imports.append(entry)
    return imports


def _extract_classes(tree: ast.Module) -> list[dict[str, Any]]:
    """Extract class definitions from AST."""
    classes: list[dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    parts = []
                    current = base
                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value
                    if isinstance(current, ast.Name):
                        parts.append(current.id)
                    bases.append(".".join(reversed(parts)))

            decorators: list[str] = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    parts = []
                    current = dec
                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value
                    if isinstance(current, ast.Name):
                        parts.append(current.id)
                    decorators.append(".".join(reversed(parts)))
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)
                    elif isinstance(dec.func, ast.Attribute):
                        parts = []
                        current = dec.func
                        while isinstance(current, ast.Attribute):
                            parts.append(current.attr)
                            current = current.value
                        if isinstance(current, ast.Name):
                            parts.append(current.id)
                        decorators.append(".".join(reversed(parts)))

            methods = _extract_functions(tree, is_method=True, class_node=node)
            docstring = ast.get_docstring(node)
            end_line = getattr(node, "end_lineno", node.lineno)
            line_count = end_line - node.lineno + 1

            cls: dict[str, Any] = {
                "name": node.name,
                "line_count": line_count,
            }
            if bases:
                cls["bases"] = bases
            if decorators:
                cls["decorators"] = decorators
            if methods:
                cls["methods"] = methods
            if docstring:
                cls["docstring"] = docstring
            classes.append(cls)
    return classes


def _extract_functions(
    tree: ast.Module,
    is_method: bool = False,
    class_node: ast.ClassDef | None = None,
) -> list[dict[str, Any]]:
    """Extract function definitions from AST."""
    functions: list[dict[str, Any]] = []

    if class_node is not None:
        nodes = [n for n in ast.iter_child_nodes(class_node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    else:
        nodes = [n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    for node in nodes:
        sig = _format_signature(node)
        is_public = not node.name.startswith("_")
        is_async = isinstance(node, ast.AsyncFunctionDef)

        decorators: list[str] = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                parts = []
                current = dec
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                decorators.append(".".join(reversed(parts)))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    parts = []
                    current = dec.func
                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value
                    if isinstance(current, ast.Name):
                        parts.append(current.id)
                    decorators.append(".".join(reversed(parts)))

        docstring = ast.get_docstring(node)
        end_line = getattr(node, "end_lineno", node.lineno)
        line_count = end_line - node.lineno + 1
        ast_size = _count_ast_nodes(node)
        nested_depth = _max_nesting_depth(node)

        func: dict[str, Any] = {
            "name": node.name,
            "signature": sig,
            "is_public": is_public,
            "line_count": line_count,
        }
        if is_async:
            func["is_async"] = True
        if is_method:
            func["is_method"] = True
        if decorators:
            func["decorators"] = decorators
        if docstring:
            func["docstring"] = docstring
        if ast_size:
            func["ast_size"] = ast_size
        if nested_depth > 2:
            func["nested_depth"] = nested_depth
        functions.append(func)
    return functions


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Format a function signature from AST."""
    parts: list[str] = []
    args = node.args

    # Positional args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        if arg.arg == "self" or arg.arg == "cls":
            continue
        part = arg.arg
        if i >= defaults_offset and defaults_offset >= 0:
            default_idx = i - defaults_offset
            if default_idx < len(args.defaults):
                part += f"={_default_repr(args.defaults[default_idx])}"
        parts.append(part)

    # *args
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")

    # keyword-only args
    for i, arg in enumerate(args.kwonlyargs):
        part = arg.arg
        if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
            part += f"={_default_repr(args.kw_defaults[i])}"
        parts.append(part)

    # **kwargs
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return "(" + ", ".join(parts) + ")"


def _default_repr(node: ast.expr) -> str:
    """Best-effort repr of a default value AST node."""
    if isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return f"{node.func.id}(...)"
        return "..."
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return "..."
    elif isinstance(node, ast.Dict):
        return "{...}"
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = _default_repr(node.operand)
        prefix = "-" if isinstance(node.op, ast.USub) else "+"
        return prefix + operand
    return "..."


def _count_ast_nodes(node: ast.AST) -> int:
    """Count total AST nodes in a subtree."""
    count = 1
    for child in ast.iter_child_nodes(node):
        count += _count_ast_nodes(child)
    return count


def _max_nesting_depth(node: ast.AST, depth: int = 0) -> int:
    """Find maximum nesting depth in an AST subtree."""
    max_d = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)):
            child_depth = depth + 1
        max_d = max(max_d, _max_nesting_depth(child, child_depth))
    return max_d


def _extract_constants(tree: ast.Module) -> list[str]:
    """Extract module-level constant names (UPPER_CASE assignments)."""
    constants: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 1:
                    constants.append(target.id)
    return sorted(constants)


def _count_lines(path: Path) -> int:
    """Count lines in a file."""
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except Exception:
        return 0


def _scan_tests(
    repo_root: Path,
    py_files: list[Path],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Scan test modules and infer relationships."""
    test_files = [f for f in py_files if _is_test_file(f, repo_root)]
    test_modules: list[dict[str, Any]] = []
    total_functions = 0
    total_classes = 0

    impl_module_paths = {m["path"] for m in modules if not _is_test_file(Path(m["path"]), repo_root)}

    for tf in test_files:
        rel = tf.relative_to(repo_root) if tf.is_relative_to(repo_root) else tf
        try:
            content = tf.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(tf))
        except SyntaxError:
            test_modules.append({"path": str(rel), "name": rel.stem, "parse_error": True})
            continue

        imports = _extract_imports(tree)
        imported_modules = [i["module"] for i in imports if i.get("module")]

        test_funcs: list[str] = []
        test_cls: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    test_funcs.append(node.name)
                    total_functions += 1
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("Test"):
                    test_cls.append(node.name)
                    total_classes += 1
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if child.name.startswith("test_"):
                                test_funcs.append(f"{node.name}.{child.name}")
                                total_functions += 1

        # Infer likely targets from imports
        likely_targets: list[str] = []
        for mod_path in impl_module_paths:
            mod_stem = Path(mod_path).stem
            for imp in imported_modules:
                if mod_stem in imp or imp.endswith(mod_stem):
                    likely_targets.append(mod_path)
                    break

        test_modules.append({
            "path": str(rel),
            "name": rel.stem,
            "imported_modules": imported_modules,
            "test_functions": test_funcs,
            "test_classes": test_cls,
            "likely_targets": sorted(set(likely_targets)),
        })

    # Compute coverage
    targeted = set()
    for tm in test_modules:
        targeted.update(tm.get("likely_targets", []))
    modules_with = sorted(targeted)
    modules_without = sorted(impl_module_paths - targeted)

    return {
        "test_modules": test_modules,
        "total_test_functions": total_functions,
        "total_test_classes": total_classes,
        "modules_with_tests": modules_with,
        "modules_without_tests": modules_without,
    }


def _is_test_file(path: Path, repo_root: Path) -> bool:
    """Check if a file is a test file."""
    rel = path.relative_to(repo_root) if path.is_relative_to(repo_root) else path
    parts = rel.parts
    name = path.stem
    return (
        name.startswith("test_")
        or name.endswith("_test")
        or "tests" in parts
        or "test" in parts
    )


def _scan_dependencies(repo_root: Path) -> dict[str, Any]:
    """Extract declared dependencies from pyproject.toml or requirements.txt."""
    result: dict[str, Any] = {}

    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            result.update(_parse_pyproject_deps(content))
        except Exception:
            pass

    # requirements.txt (runtime)
    req_file = repo_root / "requirements.txt"
    if req_file.exists():
        try:
            runtime_deps = _parse_requirements_txt(req_file)
            existing = [d["name"] for d in result.get("runtime", [])]
            for dep in runtime_deps:
                if dep["name"] not in existing:
                    result.setdefault("runtime", []).append(dep)
        except Exception:
            pass

    return result


def _parse_pyproject_deps(content: str) -> dict[str, Any]:
    """Parse dependencies from pyproject.toml content (no tomllib dependency)."""
    result: dict[str, Any] = {}
    python_version = None
    build_backend = None

    for line in content.splitlines():
        stripped = line.strip()
        # Python version
        if stripped.startswith("requires-python"):
            match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', stripped)
            if match:
                python_version = match.group(1)
        # Build backend
        if stripped.startswith("build-backend"):
            match = re.search(r'build-backend\s*=\s*["\']([^"\']+)["\']', stripped)
            if match:
                build_backend = match.group(1)

    if python_version:
        result["python_version"] = python_version
    if build_backend:
        result["build_backend"] = build_backend

    # Parse dependency lists from content
    in_deps = False
    deps_section = "runtime"
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[project]") or stripped.startswith("[project."):
            in_deps = True
            if "optional" in stripped:
                deps_section = "optional"
            else:
                deps_section = "runtime"
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            if "test" in stripped or "dev" in stripped:
                deps_section = "test" if "test" in stripped else "dev"
                in_deps = True
            continue
        if in_deps and stripped and not stripped.startswith("#"):
            match = re.match(r'["\']([^"\']+)["\']', stripped)
            if match:
                dep_str = match.group(1)
                dep = _parse_dep_string(dep_str)
                result.setdefault(deps_section, []).append(dep)

    return result


def _parse_requirements_txt(path: Path) -> list[dict[str, Any]]:
    """Parse a requirements.txt file."""
    deps: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        dep = _parse_dep_string(stripped)
        deps.append(dep)
    return deps


def _parse_dep_string(dep_str: str) -> dict[str, Any]:
    """Parse a dependency string like 'flask>=2.0' into a dict."""
    # Remove environment markers
    dep_str = dep_str.split(";")[0].strip()
    # Split name and version
    match = re.match(r'^([a-zA-Z0-9_.-]+)\s*(.*)', dep_str)
    if match:
        name = match.group(1)
        version = match.group(2).strip() or None
        result: dict[str, Any] = {"name": name, "category": "runtime"}
        if version:
            result["version_spec"] = version
        return result
    return {"name": dep_str, "category": "runtime"}


def _scan_configuration(repo_root: Path) -> list[dict[str, Any]]:
    """Discover configuration files."""
    configs: list[dict[str, Any]] = []

    # Check root-level config files
    for name in _CONFIG_NAMES:
        path = repo_root / name
        if path.exists():
            configs.append({"path": name, "kind": name})

    # Check for nested configs in common locations
    for subdir in ["src", "lib", ".github", "scripts"]:
        sub = repo_root / subdir
        if sub.is_dir():
            for name in _CONFIG_NAMES:
                path = sub / name
                if path.exists():
                    rel = f"{subdir}/{name}"
                    configs.append({"path": rel, "kind": name})

    return sorted(configs, key=lambda c: c["path"])


def _scan_cli_entry_points(repo_root: Path) -> list[dict[str, Any]]:
    """Extract console_script entry points from pyproject.toml."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return []

    try:
        content = pyproject.read_text(encoding="utf-8")
    except Exception:
        return []

    entries: list[dict[str, Any]] = []
    in_scripts = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if stripped.startswith("[") and in_scripts:
            in_scripts = False
            continue
        if in_scripts and stripped and not stripped.startswith("#"):
            match = re.match(r'(\S+)\s*=\s*["\']([^"\']+)["\']', stripped)
            if match:
                entries.append({
                    "name": match.group(1),
                    "target": match.group(2),
                })

    return entries
