"""Repository Intelligence — Language Detection.

Deterministic language and framework detection using repository evidence.
Uses file extensions, package manifests, and configuration files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# File extension to language mapping
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

# Manifest files to language mapping
_MANIFEST_MAP: dict[str, list[str]] = {
    "pyproject.toml": ["python"],
    "setup.py": ["python"],
    "setup.cfg": ["python"],
    "requirements.txt": ["python"],
    "Pipfile": ["python"],
    "poetry.lock": ["python"],
    "package.json": ["javascript", "typescript"],
    "tsconfig.json": ["typescript"],
    "Cargo.toml": ["rust"],
    "go.mod": ["go"],
    "pom.xml": ["java"],
    "Gemfile": ["ruby"],
    "composer.json": ["php"],
}

# Framework detection patterns
_FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "react": ["react", "react-dom"],
    "vue": ["vue"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
    "next": ["next"],
    "nuxt": ["nuxt"],
    "express": ["express"],
    "fastify": ["fastify"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi"],
}

# Test file patterns
_TEST_PATTERNS: dict[str, list[str]] = {
    "python": ["test_*.py", "*_test.py", "tests/"],
    "javascript": ["*.test.js", "*.test.jsx", "*.spec.js", "*.spec.jsx", "__tests__/"],
    "typescript": ["*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx", "__tests__/"],
}


def detect_languages(repo_root: Path) -> dict[str, Any]:
    """Detect languages and frameworks in a repository.

    Returns dict with:
    - languages: list of detected languages with confidence
    - frameworks: list of detected frameworks
    - primary_language: most detected language
    - file_counts: files per language
    - evidence: detection evidence
    """
    evidence: list[str] = []
    file_counts: dict[str, int] = {}
    manifest_languages: list[str] = []

    # 1. Check manifest files (highest confidence)
    for manifest, langs in _MANIFEST_MAP.items():
        if (repo_root / manifest).exists():
            manifest_languages.extend(langs)
            evidence.append(f"Found {manifest}")

    # 2. Count file extensions
    for dirpath, dirnames, filenames in repo_root.walk():
        # Skip hidden dirs and node_modules
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", ".git", "build", "dist", "venv", ".venv")
        ]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in _EXTENSION_MAP:
                lang = _EXTENSION_MAP[ext]
                file_counts[lang] = file_counts.get(lang, 0) + 1

    # 3. Compute language scores
    languages: list[dict[str, Any]] = []
    all_langs = set(list(file_counts.keys()) + manifest_languages)
    total_files = sum(file_counts.values()) or 1

    for lang in all_langs:
        count = file_counts.get(lang, 0)
        in_manifest = lang in manifest_languages
        confidence = min(1.0, (count / max(total_files, 1)) * 2) if count > 0 else 0.0
        if in_manifest:
            confidence = max(confidence, 0.8)
        languages.append({
            "language": lang,
            "confidence": round(confidence, 3),
            "file_count": count,
            "in_manifest": in_manifest,
        })

    languages.sort(key=lambda x: x["confidence"], reverse=True)

    # 4. Detect frameworks
    frameworks: list[dict[str, Any]] = []
    package_json = repo_root / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text(encoding="utf-8"))
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }
            for fw, deps in _FRAMEWORK_PATTERNS.items():
                matches = [d for d in deps if d in all_deps]
                if matches:
                    frameworks.append({
                        "framework": fw,
                        "confidence": 0.9 if len(matches) > 1 else 0.7,
                        "matched_dependencies": matches,
                    })
        except (json.JSONDecodeError, OSError):
            evidence.append("Failed to parse package.json")

    # Check Python frameworks
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            for fw, deps in _FRAMEWORK_PATTERNS.items():
                matches = [d for d in deps if d in content]
                if matches:
                    frameworks.append({
                        "framework": fw,
                        "confidence": 0.8,
                        "matched_dependencies": matches,
                    })
        except OSError:
            pass

    primary = languages[0]["language"] if languages else "unknown"

    return {
        "languages": languages,
        "frameworks": frameworks,
        "primary_language": primary,
        "file_counts": file_counts,
        "total_files": total_files,
        "evidence": evidence,
    }


def detect_project_type(repo_root: Path) -> dict[str, Any]:
    """Detect the project type and characteristics."""
    result = detect_languages(repo_root)
    pkg_json = repo_root / "package.json"
    has_pkg = pkg_json.exists()

    project_type = "unknown"
    if has_pkg:
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps:
                project_type = "react"
            elif "vue" in deps:
                project_type = "vue"
            elif "next" in deps:
                project_type = "nextjs"
            elif any(s in scripts for s in ["build", "start"]):
                project_type = "node"
        except (json.JSONDecodeError, OSError):
            pass

    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists() and project_type == "unknown":
        project_type = "python"

    return {
        **result,
        "project_type": project_type,
    }
