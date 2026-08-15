"""Repository Intelligence — JavaScript/TypeScript Scanner.

Static analysis for .js, .jsx, .mjs, .cjs, .ts, .tsx files.
Uses regex-based parsing for safe, dependency-free analysis.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .scanner_registry import COMMON_CONFIG_NAMES, RepositoryScanner

# File extensions this scanner handles
_JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

# Test file patterns
_TEST_PATTERNS = re.compile(
    r"(?:test|spec|__tests__|[Tt]est)\b",
    re.IGNORECASE,
)

# Import patterns
_IMPORT_PATTERNS = [
    re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"import\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"from\s+['\"]([^'\"]+)['\"]"),
]

# Export patterns
_EXPORT_PATTERNS = [
    re.compile(r"export\s+(?:default\s+)?(?:function|class|const|let|var|async)\s+(\w+)"),
    re.compile(r"export\s+default\s+(\w+)"),
    re.compile(r"export\s+\{([^}]+)\}"),
    re.compile(r"module\.exports\s*=\s*(\w+)"),
]

# Function patterns
_FUNCTION_PATTERNS = [
    re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
    re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>"),
    re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function"),
]

# Class patterns
_CLASS_PATTERNS = [
    re.compile(r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?"),
]

# Hook patterns (React)
_HOOK_PATTERN = re.compile(r"\b(use[A-Z]\w*)\s*\(")

# React component patterns
_COMPONENT_PATTERNS = [
    re.compile(r"(?:export\s+)?(?:default\s+)?function\s+([A-Z]\w*)\s*\("),
    re.compile(r"(?:export\s+)?const\s+([A-Z]\w*)\s*=\s*(?:\([^)]*\)|\w+)\s*=>"),
    re.compile(r"(?:export\s+)?const\s+([A-Z]\w*)\s*=\s*React\.memo"),
    re.compile(r"(?:export\s+)?const\s+([A-Z]\w*)\s*=\s*forwardRef"),
]

# Fetch/API patterns
_FETCH_PATTERNS = [
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\baxios\."),
    re.compile(r"\buseQuery\b"),
    re.compile(r"\buseMutation\b"),
]

# Route patterns
_ROUTE_PATTERNS = [
    re.compile(r"<Route\s+.*?path\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"Route\s*\(\s*\{\s*path\s*:\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"\.get\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"\.post\s*\(\s*['\"]([^'\"]+)['\"]"),
]


class JavaScriptScanner(RepositoryScanner):
    """JavaScript/TypeScript repository scanner."""

    @property
    def scanner_id(self) -> str:
        return "javascript"

    @property
    def supported_languages(self) -> tuple[str, ...]:
        return ("javascript", "typescript")

    def detect(self, repo_root: Path) -> dict[str, Any]:
        """Detect JavaScript/TypeScript files in the repository."""
        evidence: list[str] = []
        file_count = 0

        # Check for JS/TS manifest files
        for manifest in ["package.json", "tsconfig.json"]:
            if (repo_root / manifest).exists():
                evidence.append(f"Found {manifest}")

        # Count JS/TS files
        for dirpath, dirnames, filenames in repo_root.walk():
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git", "build", "dist", "venv", ".venv", "validation")
            ]
            for fname in filenames:
                if Path(fname).suffix.lower() in _JS_EXTENSIONS:
                    file_count += 1

        confidence = min(1.0, file_count / 3) if file_count > 0 else 0.0
        if any("package.json" in e for e in evidence):
            confidence = max(confidence, 0.8)

        return {
            "detected": file_count > 0 or len(evidence) > 0,
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "file_count": file_count,
        }

    def scan(self, repo_root: Path) -> dict[str, Any]:
        """Scan JavaScript/TypeScript repository."""
        modules: list[dict[str, Any]] = []
        source_files: list[dict[str, Any]] = []
        all_imports: list[dict[str, Any]] = []
        all_exports: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []
        classes_list: list[dict[str, Any]] = []
        components: list[dict[str, Any]] = []
        hooks: list[dict[str, Any]] = []
        fetch_calls: list[dict[str, Any]] = []
        routes: list[dict[str, Any]] = []
        test_files: list[str] = []
        parse_failures: list[str] = []
        file_count = 0

        for dirpath, dirnames, filenames in repo_root.walk():
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git", "build", "dist", "venv", ".venv", "validation")
            ]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                ext = fpath.suffix.lower()
                if ext not in _JS_EXTENSIONS:
                    continue

                file_count += 1
                rel_path = str(fpath.relative_to(repo_root))

                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    parse_failures.append(rel_path)
                    continue

                # Determine language
                lang = "typescript" if ext in (".ts", ".tsx") else "javascript"

                # Check if test file
                is_test = bool(_TEST_PATTERNS.search(rel_path))
                if is_test:
                    test_files.append(rel_path)

                # Parse imports
                file_imports: list[dict[str, Any]] = []
                for pattern in _IMPORT_PATTERNS:
                    for match in pattern.finditer(content):
                        file_imports.append({
                            "source": match.group(1) if match.lastindex else match.group(0),
                            "type": "esm" if "from" in match.group(0) else "commonjs",
                        })
                all_imports.extend([{"file": rel_path, **imp} for imp in file_imports])

                # Parse exports
                for pattern in _EXPORT_PATTERNS:
                    for match in pattern.finditer(content):
                        all_exports.append({
                            "file": rel_path,
                            "name": match.group(1) if match.lastindex else "default",
                        })

                # Parse functions
                for pattern in _FUNCTION_PATTERNS:
                    for match in pattern.finditer(content):
                        name = match.group(1)
                        params = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
                        functions.append({
                            "name": name,
                            "file": rel_path,
                            "params": [p.strip() for p in params.split(",") if p.strip()],
                            "is_async": "async" in match.group(0),
                        })

                # Parse classes
                for pattern in _CLASS_PATTERNS:
                    for match in pattern.finditer(content):
                        classes_list.append({
                            "name": match.group(1),
                            "file": rel_path,
                            "extends": match.group(2) if match.lastindex >= 2 else None,
                        })

                # Detect React components
                is_component = False
                for idx, pattern in enumerate(_COMPONENT_PATTERNS):
                    for match in pattern.finditer(content):
                        comp_name = match.group(1)
                        hook_count = len(_HOOK_PATTERN.findall(content))
                        is_component = True
                        components.append({
                            "name": comp_name,
                            "file": rel_path,
                            "type": "function",
                            "hook_count": hook_count,
                            "line_count": len(content.splitlines()),
                            "is_memo": idx == 2,  # Pattern index 2 is React.memo
                            "is_forward_ref": idx == 3,  # Pattern index 3 is forwardRef
                        })

                # Detect hooks
                for match in _HOOK_PATTERN.finditer(content):
                    hook_name = match.group(1)
                    # Custom hooks start with "use" followed by an uppercase letter
                    is_custom = (
                        hook_name.startswith("use")
                        and len(hook_name) > 3
                        and hook_name[3].isupper()
                    )
                    hooks.append({
                        "name": hook_name,
                        "file": rel_path,
                        "is_custom": is_custom,
                    })

                # Detect fetch/API calls
                for pattern in _FETCH_PATTERNS:
                    for match in pattern.finditer(content):
                        fetch_calls.append({
                            "file": rel_path,
                            "type": "fetch" if "fetch" in match.group(0) else "api",
                        })

                # Detect routes
                for pattern in _ROUTE_PATTERNS:
                    for match in pattern.finditer(content):
                        routes.append({
                            "path": match.group(1) if match.lastindex else match.group(0),
                            "file": rel_path,
                        })

                # Build module entry
                module_entry = {
                    "name": rel_path,
                    "file_path": rel_path,
                    "language": lang,
                    "lines_of_code": len(content.splitlines()),
                    "imports": file_imports,
                    "functions": [f for f in functions if f["file"] == rel_path],
                    "classes": [c for c in classes_list if c["file"] == rel_path],
                    "is_test": is_test,
                    "is_component": is_component,
                }
                modules.append(module_entry)
                source_files.append({
                    "path": rel_path,
                    "language": lang,
                    "size": len(content.splitlines()),
                    "is_test": is_test,
                    "is_component": is_component,
                })

        # Compute complexity signals
        complexity_signals = self._compute_complexity(modules, components, fetch_calls)
        debt_signals = self._compute_debt(modules, components, test_files, repo_root)

        return {
            "repository": {"name": repo_root.name, "path": str(repo_root), "file_count": file_count},
            "repository_languages": ["javascript", "typescript"],
            "frameworks": [],
            "modules": modules,
            "source_files": source_files,
            "imports": all_imports,
            "exports": all_exports,
            "functions": functions,
            "classes": classes_list,
            "components": components,
            "hooks": hooks,
            "fetch_calls": fetch_calls,
            "routes": routes,
            "tests": {
                "total_test_classes": 0,
                "total_test_functions": len(test_files),
                "test_files": test_files,
            },
            "dependencies": self._scan_dependencies(repo_root),
            "configuration": self._scan_configuration(repo_root),
            "cli_entry_points": [],
            "complexity_signals": complexity_signals,
            "debt_signals": debt_signals,
            "parse_failures": parse_failures,
        }

    def _scan_dependencies(self, repo_root: Path) -> dict[str, Any]:
        """Scan package.json for dependencies."""
        pkg_path = repo_root / "package.json"
        if not pkg_path.exists():
            return {}

        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            return {
                "production": list(pkg.get("dependencies", {}).keys()),
                "development": list(pkg.get("devDependencies", {}).keys()),
                "scripts": pkg.get("scripts", {}),
            }
        except (json.JSONDecodeError, OSError):
            return {}

    def _scan_configuration(self, repo_root: Path) -> list[dict[str, Any]]:
        """Scan for configuration files."""
        config_files = []
        config_names = COMMON_CONFIG_NAMES | {
            "package.json", "tsconfig.json", ".eslintrc", ".eslintrc.js",
            ".eslintrc.json", ".prettierrc", ".prettierrc.json",
            "vite.config.js", "vite.config.ts", "webpack.config.js",
            "tailwind.config.js", "tailwind.config.ts", "postcss.config.js",
            ".babelrc", "babel.config.js", "jest.config.js", "jest.config.ts",
        }
        for name in config_names:
            path = repo_root / name
            if path.exists():
                config_files.append({"kind": name, "path": name})
        return config_files

    def _compute_complexity(
        self,
        modules: list[dict[str, Any]],
        components: list[dict[str, Any]],
        fetch_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compute complexity signals for JS/TS files."""
        signals: list[dict[str, Any]] = []

        for mod in modules:
            loc = mod.get("lines_of_code", 0)
            if loc > 300:
                signals.append({
                    "type": "large_module",
                    "signal_type": "large_module",
                    "file": mod["name"],
                    "target": mod["name"],
                    "message": f"Module {mod['name']} is {loc} lines (threshold: 300)",
                    "value": loc,
                    "threshold": 300,
                    "severity": "high" if loc > 500 else "medium",
                })

        for comp in components:
            hook_count = comp.get("hook_count", 0)
            if hook_count > 5:
                signals.append({
                    "type": "high_hook_concentration",
                    "signal_type": "high_hook_concentration",
                    "file": comp["file"],
                    "target": comp["file"],
                    "message": f"Component {comp['name']} uses {hook_count} hooks (threshold: 5)",
                    "component": comp["name"],
                    "value": hook_count,
                    "threshold": 5,
                    "severity": "medium",
                })

        # Count fetch calls per file
        fetch_by_file: dict[str, int] = {}
        for fc in fetch_calls:
            fetch_by_file[fc["file"]] = fetch_by_file.get(fc["file"], 0) + 1
        for fpath, count in fetch_by_file.items():
            if count > 3:
                signals.append({
                    "type": "api_concentration",
                    "signal_type": "api_concentration",
                    "file": fpath,
                    "target": fpath,
                    "message": f"File {fpath} has {count} fetch/API calls (threshold: 3)",
                    "value": count,
                    "threshold": 3,
                    "severity": "medium",
                })

        return signals

    def _compute_debt(
        self,
        modules: list[dict[str, Any]],
        components: list[dict[str, Any]],
        test_files: list[str],
        repo_root: Path,
    ) -> list[dict[str, Any]]:
        """Compute technical debt signals."""
        signals: list[dict[str, Any]] = []

        # Check for hardcoded credentials
        for mod in modules:
            try:
                content = (repo_root / mod["name"]).read_text(encoding="utf-8", errors="replace")
                if re.search(r"(?:password|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]+['\"]", content, re.IGNORECASE):
                    signals.append({
                        "type": "hardcoded_credential",
                        "file": mod["name"],
                        "severity": "high",
                        "evidence": "Credential-like literal found in source",
                    })
            except Exception:
                pass

        # Check for missing tests
        tested_files = set()
        for tf in test_files:
            # Map test file to source file
            base = Path(tf).name.replace(".test.", ".").replace(".spec.", ".")
            tested_files.add(base)

        for mod in modules:
            if not mod.get("is_test"):
                src_name = Path(mod["name"]).name
                if src_name not in tested_files and not mod["name"].endswith(".config.js"):
                    signals.append({
                        "type": "missing_test",
                        "file": mod["name"],
                        "severity": "low",
                        "evidence": "No corresponding test file found",
                    })
                    break  # Only report once

        # Check for large components
        for comp in components:
            if comp.get("line_count", 0) > 200:
                signals.append({
                    "type": "large_component",
                    "file": comp["file"],
                    "component": comp["name"],
                    "value": comp["line_count"],
                    "severity": "medium",
                    "evidence": f"Component has {comp['line_count']} lines",
                })

        return signals
