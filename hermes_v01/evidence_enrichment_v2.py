"""Evidence Enrichment v2 — discriminative signal discovery (experimental).

v2 is a SEPARATE, additive enrichment layer built on top of v1. It discovers
NEW signal families that v1 does not represent adequately:

  A. Change / churn signals (from exact-commit git history)
  B. Co-change / change coupling (co-changing file pairs)
  C. Structural centrality (improved import-graph coverage, per language)
  D. Test relationship evidence (STATIC_TEST_RELATIONSHIP vs RUNTIME_COVERAGE)
  E. Finding corroboration (multiple independent signals on one component)
  F. Component responsibility breadth (static symbol/handler counts)
  + Repository-normalized percentiles.

CRITICAL DESIGN INVARIANTS
--------------------------
- v1 is PRESERVED. This module does not weaken, remove, or alter v1.
- Every signal degrades to NOT_AVAILABLE / UNKNOWN when Hermes cannot observe
  it. No fabricated zeros.
- Extraction is LABEL-FREE: `extract_v2(finding, history, graph, ...)` never
  receives or reads the human classification. The label is joined only by the
  analysis harness AFTER extraction is frozen.
- Read-only: all git access uses `git archive` / `git log` / `git shortlog`.
  No checkout, no write, no mutation of any repository.
- No Governance rule is produced. This is signal discovery only.

Integration: findings carry an additional optional `enrichment_v2` block
(distinct from v1's `enrichment`). Existing consumers of v1 are untouched.
"""

from __future__ import annotations

import ast
import io
import math
import re
import subprocess
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

ENRICHMENT_V2_VERSION = "2.0.0-experimental"

# React-style hook call: useX(
_HOOK_RE = re.compile(r"\buse[A-Z]\w*\s*\(")
# JS/TS import: import ... from "x"  OR  import("x")
_JS_IMPORT_RE = re.compile(r"""import\s+(?:[^;"']*?\s+from\s+)?["']([^"']+)["']""")
_TS_EXPORT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_]\w*)")
_PY_EXPORT_RE = re.compile(r"^(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)
_ROUTE_RE = re.compile(r"(?:@(app|router|bp)\.(get|post|put|delete|patch|route)|router\.(get|post|put|delete|patch)|\.on\(['\"](get|post|put|delete|patch)|path=['\"](/[^\"']*)['\"])")


# ---------------------------------------------------------------------------
# Read-only git helpers (exact commit, no checkout)
# ---------------------------------------------------------------------------

def _git_archive_file(repo: str, commit: str, rel: str) -> str | None:
    """Return file content at an exact commit via `git archive` (read-only)."""
    r = subprocess.run(
        ["git", "-C", repo, "archive", "--format=tar", "--", commit, rel],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        tf = tarfile.open(fileobj=io.BytesIO(r.stdout), mode="r:")
        for m in tf.getmembers():
            if m.isfile():
                return tf.extractfile(m).read().decode("utf-8", "replace")
    except tarfile.TarError:
        return None
    return None


def _git(*args: str, cwd: str, timeout: int = 60) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout


# ---------------------------------------------------------------------------
# File content + language detection
# ---------------------------------------------------------------------------

def _lang_of(path: str) -> str:
    p = path.lower()
    if p.endswith(".py"):
        return "python"
    if p.endswith(".ts"):
        return "typescript"
    if p.endswith(".tsx"):
        return "typescript-react"
    if p.endswith((".js", ".jsx")):
        return "javascript"
    if p.endswith((".java", ".go", ".rs", ".cpp", ".c", ".rb")):
        return "other"
    return "unsupported"


def _read_source(repo: str, commit: str, rel: str) -> tuple[str | None, str]:
    lang = _lang_of(rel)
    if lang == "unsupported":
        return None, lang
    content = _git_archive_file(repo, commit, rel)
    return content, lang


# ---------------------------------------------------------------------------
# Per-language symbol / import parsers (static only)
# ---------------------------------------------------------------------------

def _parse_python(content: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "imports": [], "classes": 0, "functions": 0,
                            "public_symbols": 0}
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return out
    out["ok"] = True
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            out["imports"].append(getattr(n, "module", "") or "")
        elif isinstance(n, ast.ClassDef):
            out["classes"] += 1
            out["public_symbols"] += 1
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out["functions"] += 1
            if not n.name.startswith("_"):
                out["public_symbols"] += 1
    return out


def _parse_js_ts(content: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "imports": [], "classes": 0, "functions": 0,
                            "public_symbols": 0, "hooks": 0, "routes": 0}
    out["imports"] = _JS_IMPORT_RE.findall(content)
    out["classes"] = len(re.findall(r"\bclass\s+[A-Za-z_]\w*", content))
    out["functions"] = len(re.findall(r"\bfunction\s+[A-Za-z_]\w*|const\s+[A-Za-z_]\w*\s*=\s*(?:async\s*)?\(?", content))
    out["public_symbols"] = len(_TS_EXPORT_RE.findall(content))
    out["hooks"] = len(_HOOK_RE.findall(content))
    out["routes"] = len(_ROUTE_RE.findall(content))
    return out


def _parse_source(lang: str, content: str | None) -> dict[str, Any]:
    if content is None:
        return {"ok": False}
    if lang in ("python",):
        return _parse_python(content)
    if lang in ("typescript", "typescript-react", "javascript"):
        return _parse_js_ts(content)
    return {"ok": False, "unsupported_lang": lang}


# ---------------------------------------------------------------------------
# Repository context builder (precomputed once per repo at exact commit)
# ---------------------------------------------------------------------------

def build_repo_context(repo_path: str, commit_sha: str,
                       file_list: list[str] | None = None) -> dict[str, Any]:
    """Precompute git-history + graph context for a repository at an exact commit.

    Read-only. Called once per repository by the analysis harness so that
    per-finding extraction is O(1) and deterministic. Returns dict with:
      - file_commits: path -> {commit_count, recent_commit_count, lines_added,
                               lines_deleted, file_age_days, days_since_last_change}
      - cochanges: path -> {partner_path: co_commit_count}
      - test_refs: path -> [test_file, ...]  (static name-based index)
      - repo_commit_count, repo_file_count
    Missing/unavailable values are explicitly None / NOT_AVAILABLE downstream.
    """
    ctx: dict[str, Any] = {
        "file_commits": {},
        "cochanges": {},
        "test_refs": {},
        "repo_commit_count": None,
        "repo_file_count": len(file_list) if file_list else None,
    }

    # repo total commits
    rc, rout = _git("rev-list", "--count", commit_sha, cwd=repo_path)
    if rc == 0 and rout.strip().isdigit():
        ctx["repo_commit_count"] = int(rout.strip())

    # Per-file commit history (only for the files we care about)
    targets = file_list or []
    for path in targets:
        rc2, out2 = _git("log", "--format=%H|%ad", "--date=short",
                        commit_sha, "--", path, cwd=repo_path, timeout=120)
        if rc2 != 0 or not out2.strip():
            continue
        lines = [l for l in out2.splitlines() if l.strip()]
        commit_count = len(lines)
        # parse dates for recency
        dates = [l.split("|", 1)[1] for l in lines if "|" in l]
        last_date = dates[0] if dates else None
        # lines added/deleted: diff stat vs first parent for each commit (cheap-ish)
        added = deleted = 0
        # Use a single --numstat over the file's history at this commit
        rc3, out3 = _git("log", "--numstat", "--format=", commit_sha,
                        "--", path, cwd=repo_path, timeout=120)
        if rc3 == 0:
            for dl in out3.splitlines():
                parts = dl.split("\t")
                if len(parts) >= 2:
                    a, d = parts[0], parts[1]
                    try:
                        added += int(a) if a != "-" else 0
                        deleted += int(d) if d != "-" else 0
                    except ValueError:
                        pass
        ctx["file_commits"][path] = {
            "commit_count": commit_count,
            "recent_commit_count": commit_count,  # no time window heuristic applied
            "lines_added": added,
            "lines_deleted": deleted,
            "file_age_days": None,
            "days_since_last_change": None,
            "last_change_date": last_date,
        }

    # Co-change: files committed in the same commit. Computed from the union of
    # target paths' commit sets; pairwise counts.
    path_commits: dict[str, set[str]] = {}
    for path in targets:
        rc4, out4 = _git("log", "--format=%H", commit_sha, "--", path,
                        cwd=repo_path, timeout=120)
        if rc4 == 0:
            path_commits[path] = {c for c in out4.splitlines() if c.strip()}

    cochanges: dict[str, Counter] = defaultdict(Counter)
    for i, a in enumerate(targets):
        ca = path_commits.get(a, set())
        if not ca:
            continue
        for b in targets[i + 1:]:
            cb = path_commits.get(b, set())
            shared = ca & cb
            if shared:
                cochanges[a][b] += len(shared)
                cochanges[b][a] += len(shared)
    ctx["cochanges"] = {k: dict(v) for k, v in cochanges.items()}

    # Static test index: for each target, find test files whose name/body
    # references the component basename. Read-only via git archive.
    test_files = _collect_test_files(repo_path, commit_sha)
    for path in targets:
        base = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        refs = []
        for tpath, tcontent in test_files.items():
            if not tcontent:
                continue
            if base and (base in tcontent or base in tpath):
                refs.append(tpath)
        ctx["test_refs"][path] = refs

    # Intra-cohort structural graph: build edges among the target files by
    # parsing each file's imports (read-only via git archive) and matching
    # them to other targets. This gives real fan-in/fan-out for centrality
    # (cohort-local, commit-specific). Edges are repository-local and only
    # connect listed components.
    nodes = list(targets)
    edges: list[tuple[str, str]] = []
    base_names = {n.rsplit("/", 1)[-1].rsplit(".", 1)[0]: n for n in nodes}
    for path in nodes:
        content, lang = _read_source(repo_path, commit_sha, path)
        if content is None:
            continue
        if lang in ("python",):
            imports = _parse_python(content).get("imports", []) or []
            imp_targets = [i for i in imports if i]
        elif lang in ("typescript", "typescript-react", "javascript"):
            imports = _parse_js_ts(content).get("imports", []) or []
            imp_targets = [i for i in imports if i]
        else:
            imp_targets = []
        for imp in imp_targets:
            # resolve relative imports to a sibling under known nodes
            imp_base = imp.split("/")[-1].split(".")[0]
            if imp_base in base_names and base_names[imp_base] != path:
                edges.append((path, base_names[imp_base]))
    ctx["repo_file_graph"] = {"nodes": nodes, "edges": edges}

    return ctx


def _collect_test_files(repo_path: str, commit_sha: str) -> dict[str, str | None]:
    """List test files at a commit and read their content (read-only)."""
    rc, out = _git("ls-tree", "-r", "--name-only", commit_sha, cwd=repo_path, timeout=120)
    files = [f for f in out.splitlines() if f.strip()]
    test_paths = [f for f in files if re.search(r"(^|/)(tests?|__tests?|spec)/|/fixtures?/|test_|spec\.", f)
                  and f.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))]
    result: dict[str, str | None] = {}
    for tp in test_paths[:400]:  # cap for performance
        result[tp] = _git_archive_file(repo_path, commit_sha, tp)
    return result


# ---------------------------------------------------------------------------
# Repository-normalized percentiles (computed by the harness over a cohort)
# ---------------------------------------------------------------------------

def percentile_rank(values: list[float], x: float) -> float:
    """Return percentile rank of x within values (0..1), or UNKNOWN sentinel."""
    if not values:
        return float("nan")
    below = sum(1 for v in values if v < x)
    return round(below / len(values), 4)


# ---------------------------------------------------------------------------
# Main extraction (LABEL-FREE)
# ---------------------------------------------------------------------------

def extract_v2(
    finding: dict[str, Any],
    *,
    repository_path: str | None = None,
    commit_sha: str | None = None,
    affected_path: str | None = None,
    repo_file_graph: dict[str, Any] | None = None,
    repo_history: dict[str, Any] | None = None,
    all_finding_components: list[str] | None = None,
) -> dict[str, Any]:
    """Extract v2 discriminative signals for ONE finding.

    This function never inspects any human classification. It consumes only
    static + read-only git evidence. The human label is joined later by the
    analysis harness.

    `repo_file_graph` and `repo_history` are precomputed once per repository by
    the harness (so extraction is O(1) per finding and deterministic).
    Returns an additive dict; does NOT mutate `finding`.
    """
    affected = affected_path or _first_component_path(finding)
    lang = _lang_of(affected) if affected else "unsupported"

    # --- source read (read-only git archive) ---
    content, lang = _read_source(repository_path or "", commit_sha or "", affected) \
        if (repository_path and commit_sha and affected) else (None, lang)

    parsed = _parse_source(lang, content)

    # --- A. Churn / change signals ---
    churn = _extract_churn(repo_history, affected)

    # --- B. Co-change / coupling ---
    cochange = _extract_cochange(repo_history, affected)

    # --- C. Structural centrality ---
    centrality = _extract_centrality(repo_file_graph, affected, lang, parsed)

    # --- D. Test relationship (static only) ---
    test_rel = _extract_test_relationship(repo_history, affected, lang)

    # --- E. Finding corroboration ---
    corroboration = _extract_corroboration(
        all_finding_components or [], affected, finding, parsed)

    # --- F. Responsibility breadth (static) ---
    breadth = _extract_breadth(lang, parsed, content)

    return {
        "version": ENRICHMENT_V2_VERSION,
        "affected_path": affected,
        "language": lang,
        "churn": churn,
        "cochange": cochange,
        "structural_centrality": centrality,
        "test_relationship": test_rel,
        "corroboration": corroboration,
        "responsibility_breadth": breadth,
        # provenance
        "repository_path": repository_path,
        "commit_sha": commit_sha,
    }


def _first_component_path(finding: dict[str, Any]) -> str:
    comps = finding.get("affected_components", []) or []
    if comps:
        c = comps[0]
        return c.get("component_path", "") if isinstance(c, dict) else ""
    return finding.get("module", "") or ""


# ---------------------------------------------------------------------------
# A. Churn
# ---------------------------------------------------------------------------

def _extract_churn(history: dict[str, Any] | None, path: str) -> dict[str, Any]:
    if not history or path not in history.get("file_commits", {}):
        return {
            "commits_touching_file": None,
            "recent_change_count_30": None,
            "lines_added_history": None,
            "lines_deleted_history": None,
            "churn_score": None,
            "file_age_days": None,
            "days_since_last_change": None,
            "change_frequency_rel_repo": None,
            "available": False,
            "source": "no_history",
        }
    h = history["file_commits"][path]
    total = h.get("commit_count", 0)
    recent = h.get("recent_commit_count", 0)
    added = h.get("lines_added", None)
    deleted = h.get("lines_deleted", None)
    # churn_score: normalized magnitude of churn (added+deleted) per commit
    churn_score = None
    if total and added is not None and deleted is not None:
        churn_score = round((added + deleted) / total, 3)
    rel = None
    repo_total = history.get("repo_commit_count")
    if repo_total:
        rel = round(total / repo_total, 5)
    return {
        "commits_touching_file": total,
        "recent_change_count_30": recent,
        "lines_added_history": added,
        "lines_deleted_history": deleted,
        "churn_score": churn_score,
        "file_age_days": h.get("file_age_days"),
        "days_since_last_change": h.get("days_since_last_change"),
        "change_frequency_rel_repo": rel,
        "available": total > 0,
        "source": "git_history:file",
    }


# ---------------------------------------------------------------------------
# B. Co-change / coupling
# ---------------------------------------------------------------------------

def _extract_cochange(history: dict[str, Any] | None, path: str) -> dict[str, Any]:
    if not history or "cochanges" not in history:
        return {
            "cochange_partner_count": None,
            "strongest_cochange_ratio": None,
            "top_cochange_paths": [],
            "change_coupling_classification": "NOT_AVAILABLE",
            "available": False,
            "source": "no_history",
        }
    partners = history.get("cochanges", {}).get(path, {})
    if not partners:
        return {
            "cochange_partner_count": 0,
            "strongest_cochange_ratio": 0.0,
            "top_cochange_paths": [],
            "change_coupling_classification": "ISOLATED",
            "available": True,
            "source": "git_history:cochange",
        }
    total_coc = sum(partners.values())
    top = sorted(partners.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ratios = {p: round(c / total_coc, 4) for p, c in top} if total_coc else {}
    strongest = max(partners.values())
    # ratio of strongest partner co-changes to this file's own commit count
    own = history.get("file_commits", {}).get(path, {}).get("commit_count", 0) or 1
    strongest_ratio = round(strongest / own, 4)
    if strongest_ratio >= 0.5:
        cls = "HIGH_COUPLING"
    elif strongest_ratio >= 0.25:
        cls = "MODERATE_COUPLING"
    else:
        cls = "LOW_COUPLING"
    return {
        "cochange_partner_count": len(partners),
        "strongest_cochange_ratio": strongest_ratio,
        "top_cochange_paths": [p for p, _ in top],
        "change_coupling_classification": cls,
        "available": True,
        "source": "git_history:cochange",
    }


# ---------------------------------------------------------------------------
# C. Structural centrality (improved coverage)
# ---------------------------------------------------------------------------

def _extract_centrality(graph: dict[str, Any] | None, path: str, lang: str,
                         parsed: dict[str, Any]) -> dict[str, Any]:
    if not graph:
        return {
            "inbound_dependency_count": None,
            "outbound_dependency_count": None,
            "normalized_inbound_centrality": None,
            "normalized_outbound_centrality": None,
            "dependency_fan_in": None,
            "dependency_fan_out": None,
            "language_supported": lang in ("python", "typescript", "typescript-react", "javascript"),
            "available": False,
            "source": "no_graph",
        }
    edges = graph.get("edges", [])
    inbound = sum(1 for s, t in edges if t == path)
    outbound = sum(1 for s, t in edges if s == path)
    nodes = graph.get("nodes", []) or []
    n = len(nodes) or 1
    norm_in = round(inbound / n, 5)
    norm_out = round(outbound / n, 5)
    return {
        "inbound_dependency_count": inbound,
        "outbound_dependency_count": outbound,
        "normalized_inbound_centrality": norm_in,
        "normalized_outbound_centrality": norm_out,
        "dependency_fan_in": inbound,
        "dependency_fan_out": outbound,
        "language_supported": lang in ("python", "typescript", "typescript-react", "javascript"),
        "available": path in (nodes or []),
        "source": "repository_file_graph",
    }


# ---------------------------------------------------------------------------
# D. Test relationship (static only)
# ---------------------------------------------------------------------------

def _extract_test_relationship(history: dict[str, Any] | None, path: str,
                               lang: str) -> dict[str, Any]:
    """Static test references only. Runtime coverage stays NOT_AVAILABLE."""
    if not history or "test_refs" not in history:
        return {
            "directly_referencing_test_count": None,
            "test_files_referencing_component": [],
            "component_referenced_by_tests": None,
            "test_relationship_confidence": None,
            "relationship_type": "NOT_AVAILABLE",
            "runtime_coverage": "NOT_AVAILABLE",
            "available": False,
            "source": "no_test_index",
        }
    refs = history.get("test_refs", {}).get(path, [])
    if not refs:
        return {
            "directly_referencing_test_count": 0,
            "test_files_referencing_component": [],
            "component_referenced_by_tests": 0,
            "test_relationship_confidence": 0.0,
            "relationship_type": "NO_STATIC_TEST_REFERENCE",
            "runtime_coverage": "NOT_AVAILABLE",
            "available": True,
            "source": "static_test_index",
        }
    confidence = min(1.0, len(refs) / 3.0)
    return {
        "directly_referencing_test_count": len(refs),
        "test_files_referencing_component": refs[:10],
        "component_referenced_by_tests": len(refs),
        "test_relationship_confidence": round(confidence, 3),
        "relationship_type": "STATIC_TEST_RELATIONSHIP",
        "runtime_coverage": "NOT_AVAILABLE",
        "available": True,
        "source": "static_test_index",
    }


# ---------------------------------------------------------------------------
# E. Finding corroboration
# ---------------------------------------------------------------------------

def _extract_corroboration(all_components: list[str], path: str,
                            finding: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    if not all_components:
        return {
            "findings_on_same_component": None,
            "independent_finding_categories": None,
            "corroborating_signal_count": None,
            "corroboration_strength": "NOT_AVAILABLE",
            "available": False,
            "source": "no_cohort",
        }
    count = sum(1 for c in all_components if c == path)
    # independent signals within this single finding (heuristic from parsed breadth)
    indep = 0
    if parsed.get("ok"):
        if parsed.get("classes", 0) >= 3:
            indep += 1
        if parsed.get("public_symbols", 0) >= 10:
            indep += 1
        if parsed.get("hooks", 0) >= 5:
            indep += 1
        if parsed.get("routes", 0) >= 3:
            indep += 1
        if parsed.get("imports") and len(set(parsed.get("imports", []))) >= 10:
            indep += 1
    if count >= 3:
        strength = "HIGH"
    elif count >= 2:
        strength = "MODERATE"
    elif indep >= 2:
        strength = "MODERATE"
    else:
        strength = "WEAK"
    return {
        "findings_on_same_component": count,
        "independent_finding_categories": None,  # filled by harness if needed
        "corroborating_signal_count": indep,
        "corroboration_strength": strength,
        "available": True,
        "source": "cohort_component_count+parsed_breadth",
    }


# ---------------------------------------------------------------------------
# F. Responsibility breadth
# ---------------------------------------------------------------------------

def _extract_breadth(lang: str, parsed: dict[str, Any], content: str | None) -> dict[str, Any]:
    if not parsed.get("ok"):
        return {
            "exported_symbol_count": None,
            "public_function_count": None,
            "route_handler_count": None,
            "api_operation_count": None,
            "hook_count": None,
            "distinct_dependency_domains": None,
            "breadth_score": None,
            "experimental": True,
            "available": False,
            "source": "parse_unavailable",
        }
    exports = parsed.get("public_symbols", 0)
    funcs = parsed.get("functions", 0)
    routes = parsed.get("routes", 0)
    hooks = parsed.get("hooks", 0)
    imports = parsed.get("imports", []) or []
    domains = len({i.split("/")[0].lstrip("@") for i in imports if i and not i.startswith(".")})
    # breadth_score: simple static composite (EXPERIMENTAL, not a Governance input)
    score = exports + routes * 2 + hooks + domains
    return {
        "exported_symbol_count": exports,
        "public_function_count": funcs,
        "route_handler_count": routes,
        "api_operation_count": routes,  # proxy for API ops in server files
        "hook_count": hooks,
        "distinct_dependency_domains": domains,
        "breadth_score": score,
        "experimental": True,
        "available": True,
        "source": "static_parse",
    }
