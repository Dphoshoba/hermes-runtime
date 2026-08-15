"""Evidence Enrichment v1.0.0 — additive, deterministic, read-only.

Goal: improve Governance's *evidence* for distinguishing
USEFUL / NEEDS_MORE_EVIDENCE / NOT_ACTIONABLE without changing any
Governance decision logic.

This module is an enrichment layer only. It:
- attaches a `finding["enrichment"]` block to each Engineering Intelligence
  finding (additive; existing fields untouched);
- derives signals from (a) the finding's own evidence, (b) the Repository
  Intelligence model, and (c) read-only git history at the EXACT materialized
  commit;
- uses explicit `UNKNOWN` / `NOT_AVAILABLE` / `NOT_OBSERVED` for anything
  EVOSIA cannot directly observe (no invented behavioral/runtime evidence);
- never mutates a target repository, never checks out a commit, never writes
  outside the enrichment dict.

Integration point: called inside `analyze_engineering` (the EI boundary),
immediately after findings are generated. This adds no canonical pipeline
stage and does not alter SCAN_STAGES.

Every enrichment block carries provenance:
    enrichment_version, repository_identifier, commit_sha, affected_path,
    + per-signal source references.
"""

from __future__ import annotations

import functools
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

ENRICHMENT_VERSION = "1.0.0"

# Threshold used by the static analyzers for "large module" (repo_analyzer).
# Kept here as documentation; enrichment magnitude uses the observed value
# and a 300-line threshold consistent with the Cycle 7 frozen dataset labels.
DEFAULT_LARGE_MODULE_THRESHOLD = 300

EXCEEDANCE_TIERS = [
    ("EXTREME", 3.0),
    ("HIGH", 2.0),
    ("MODERATE", 1.5),
    ("NOTABLE", 1.2),
    ("LOW", 1.0),
]


# ---------------------------------------------------------------------------
# Provenance-carrying signal result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signal:
    """A single enriched signal with source provenance."""
    name: str
    value: Any
    classification: str   # e.g. STRUCTURAL_IMPORTANCE, UNKNOWN
    source: str           # where the value came from
    available: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "classification": self.classification,
            "source": self.source,
            "available": self.available,
        }


# ---------------------------------------------------------------------------
# File-context classification
# ---------------------------------------------------------------------------

def _endswith_env(p: str) -> bool:
    return p.endswith(".env") or p.rsplit("/", 1)[-1] in (
        "package.json", "pyproject.toml", "setup.cfg", "tsconfig.json",
    ) or "/config/" in p or "/configuration/" in p


def classify_file_context(affected_path: str) -> tuple[str, str]:
    """Classify a path into a FileContext enum value.

    Returns (context, source). Uses only the path string — no behavioral
    inference. Falls back to UNKNOWN when the path is missing.
    """
    if not affected_path:
        return "UNKNOWN", "no_affected_path"
    p = affected_path.lower()
    name = p.rsplit("/", 1)[-1]

    # VENDOR / GENERATED (check before TEST/CONFIG; some match loosely)
    if (
        "/vendor/" in p
        or "node_modules/" in p
        or "/node_modules/" in p
        or "/__pycache__/" in p
        or "/migrations/versions/" in p
        or "/generated/" in p
        or name == "__init__.py"
    ):
        if name == "__init__.py":
            return "GENERATED", "path_pattern:init"
        return "VENDOR", "path_pattern"

    # FIXTURE (before TEST so /tests/fixtures/ is not caught by /test/)
    if (
        "/fixtures/" in p
        or "/fixture/" in p
        or name.startswith("fixture")
        or "/test_data/" in p
        or "/testdata/" in p
    ):
        return "FIXTURE", "path_pattern"

    # TEST
    if (
        "/test" in p
        or p.startswith("test")
        or name.startswith("test_")
        or name.endswith("_test.py")
        or "/tests/" in p
        or "/__tests__/" in p
        or p.endswith(".test.tsx")
        or p.endswith(".test.ts")
        or p.endswith(".test.jsx")
        or p.endswith(".test.js")
        or "/spec/" in p
    ):
        return "TEST", "path_pattern"

    # CONFIGURATION
    if (
        p.endswith(".toml")
        or p.endswith(".yaml")
        or p.endswith(".yml")
        or p.endswith(".json")
        or p.endswith(".ini")
        or _endswith_env(p)
    ):
        return "CONFIGURATION", "path_pattern"

    # DOCUMENTATION
    if (
        p.endswith(".md")
        or p.endswith(".rst")
        or p.endswith(".txt")
        or "/docs/" in p
        or "/documentation/" in p
    ):
        return "DOCUMENTATION", "path_pattern"

    # PRODUCTION (default for source modules)
    if (
        p.endswith(".py")
        or p.endswith(".ts")
        or p.endswith(".tsx")
        or p.endswith(".js")
        or p.endswith(".jsx")
        or p.endswith(".java")
        or p.endswith(".go")
        or p.endswith(".rs")
        or p.endswith(".cpp")
        or p.endswith(".c")
    ):
        return "PRODUCTION", "path_pattern"

    return "UNKNOWN", "path_pattern:unrecognized"


# ---------------------------------------------------------------------------
# Magnitude / exceedance
# ---------------------------------------------------------------------------

def compute_exceedance(observed_value: float | None, threshold: float | None) -> dict[str, Any]:
    """Compute exceedance_ratio and tier from observed vs threshold."""
    if observed_value is None or threshold is None or threshold <= 0:
        return {
            "observed_value": observed_value,
            "threshold_value": threshold,
            "exceedance_ratio": None,
            "exceedance_tier": "UNKNOWN",
            "available": False,
            "source": "no_observed_value",
        }
    ratio = observed_value / threshold
    tier = "LOW"
    for tname, tval in EXCEEDANCE_TIERS:
        if ratio >= tval:
            tier = tname
            break
    return {
        "observed_value": observed_value,
        "threshold_value": threshold,
        "exceedance_ratio": round(ratio, 4),
        "exceedance_tier": tier,
        "available": True,
        "source": "observed_vs_threshold",
    }


# ---------------------------------------------------------------------------
# Structural importance via RI module graph (read-only in-memory)
# ---------------------------------------------------------------------------

def compute_structural_importance(ri: dict[str, Any], affected_path: str) -> dict[str, Any]:
    """Inbound/outbound import counts + centrality from the RI module graph.

    Source: repository_intelligence module_graph (already computed, no new scan).
    """
    graph = ri.get("module_graph", {}) or {}
    edges = graph.get("edges", []) or []
    nodes = set(graph.get("nodes", []) or [])

    inbound = 0
    outbound = 0
    for src, tgt in edges:
        if tgt == affected_path:
            inbound += 1
        if src == affected_path:
            outbound += 1

    if affected_path in nodes:
        total_deg = inbound + outbound
        if total_deg >= 10:
            centrality = "HIGH"
        elif total_deg >= 4:
            centrality = "MODERATE"
        elif total_deg >= 1:
            centrality = "LOW"
        else:
            centrality = "ISOLATED"
        available = True
        source = "repository_intelligence:module_graph"
    else:
        total_deg = 0
        centrality = "UNKNOWN"
        available = False
        source = "module_not_in_graph"

    return {
        "inbound_dependency_count": inbound,
        "outbound_dependency_count": outbound,
        "total_degree": total_deg,
        "centrality_classification": centrality,
        "available": available,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Evidence strength
# ---------------------------------------------------------------------------

def compute_evidence_strength(finding: dict[str, Any]) -> dict[str, Any]:
    """Evidence strength from the finding's own evidence references."""
    refs = finding.get("evidence_references", []) or []
    n = len(refs)
    sources = {e.get("source", "") for e in refs if e.get("source")}
    paths = {e.get("reference_path", "") for e in refs if e.get("reference_path")}
    distinct_paths = len([p for p in paths if p])

    if n == 0:
        strength = "NONE"
        available = False
    elif n >= 3 and len(sources) >= 2:
        strength = "STRONG"
        available = True
    elif n >= 2:
        strength = "MODERATE"
        available = True
    else:
        strength = "WEAK"
        available = True

    return {
        "evidence_reference_count": n,
        "independent_evidence_type_count": len(sources),
        "distinct_reference_path_count": distinct_paths,
        "evidence_strength": strength,
        "available": available,
        "source": "finding_evidence_references",
    }


# ---------------------------------------------------------------------------
# Git history enrichment (read-only)
# ---------------------------------------------------------------------------

def _git(*args: str, cwd: str, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout
    except Exception as exc:  # noqa: BLE001 - read-only best-effort
        return 1, f"error:{exc}"


# Per-file git evidence is derived from ONE bounded repository-history
# operation per (repository, commit) instead of one subprocess per finding.
# git log emits commits newest-first; each commit block is:
#   <SENTINEL><hash>|<committer-date>|<author-email>
#   <changed-file-1>
#   <changed-file-2>
#   (blank line)
# We parse this once into a per-file history map and reuse it across every
# finding that references the same repository/commit.
_GIT_CONTEXT_SENTINEL = "___COMMITSEP___"


@dataclass(frozen=True)
class _RepoGitContext:
    # affected_path (repo-relative) -> list of (commit, date, email), newest first
    file_history: dict[str, list[tuple[str, str, str]]]


@functools.lru_cache(maxsize=16)
def _build_repo_git_context(
    repo_local_path: str, commit_sha: str
) -> _RepoGitContext | None:
    """One bounded git history parse for a repository at an exact commit.

    Read-only: uses `git log <commit> --name-only`. Never checks out or
    writes. Returns None when git is unavailable or history is empty so
    callers fall back to NOT_OBSERVED / UNKNOWN semantics.
    """
    rc, out = _git(
        "log", commit_sha, "--name-only",
        f"--format={_GIT_CONTEXT_SENTINEL}%H|%ci|%ae",
        cwd=repo_local_path, timeout=120,
    )
    if rc != 0 or not out.strip():
        return None

    file_history: dict[str, list[tuple[str, str, str]]] = {}
    cur_commit = cur_date = cur_email = None
    for raw in out.splitlines():
        line = raw.rstrip("\n")
        if line.startswith(_GIT_CONTEXT_SENTINEL):
            body = line[len(_GIT_CONTEXT_SENTINEL):]
            parts = body.split("|", 2)
            cur_commit = parts[0] if parts else None
            cur_date = parts[1] if len(parts) > 1 else None
            cur_email = parts[2] if len(parts) > 2 else None
            continue
        if not line.strip():
            continue
        rel = line.strip()
        if rel.startswith("/"):
            rel = rel.lstrip("/")
        file_history.setdefault(rel, []).append((cur_commit, cur_date, cur_email))

    return _RepoGitContext(file_history=file_history)


def _rel_path(affected_path: str) -> str:
    rel = affected_path
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    return rel


def compute_change_history(
    repo_local_path: str | None,
    commit_sha: str | None,
    affected_path: str,
) -> dict[str, Any]:
    """Change history for the affected path at the exact commit (read-only).

    Derived in-memory from a single repository-history parse (see
    _build_repo_git_context); no per-finding git subprocess.
    """
    if not repo_local_path or not affected_path:
        return {
            "commit_count": None,
            "recent_change_count": None,
            "last_changed_commit": None,
            "last_changed_at": None,
            "churn_classification": "UNKNOWN",
            "available": False,
            "source": "no_repo_or_path",
        }
    rel = _rel_path(affected_path)
    ctx = _build_repo_git_context(repo_local_path, commit_sha or "HEAD")
    if ctx is None or rel not in ctx.file_history:
        return {
            "commit_count": 0,
            "recent_change_count": 0,
            "last_changed_commit": None,
            "last_changed_at": None,
            "churn_classification": "NOT_OBSERVED",
            "available": False,
            "source": f"git_log:no_history:{rel}",
        }

    entries = ctx.file_history[rel]
    commit_count = len(entries)
    # git log is newest-first; entries[0] is the most recent change at-or-before
    # the exact scanned commit (git log <commit> already bounds the walk).
    last_changed_commit, last_changed_at, _ = entries[0]

    if commit_count >= 10:
        churn = "HIGH"
    elif commit_count >= 4:
        churn = "MODERATE"
    elif commit_count >= 1:
        churn = "LOW"
    else:
        churn = "NONE"

    return {
        "commit_count": commit_count,
        "recent_change_count": commit_count,  # full history available; no time-window heuristic
        "last_changed_commit": last_changed_commit,
        "last_changed_at": last_changed_at,
        "churn_classification": churn,
        "available": True,
        "source": "git_log:file_history",
    }


def compute_ownership(
    repo_local_path: str | None,
    commit_sha: str | None,
    affected_path: str,
) -> dict[str, Any]:
    """Ownership / responsibility concentration from git history (read-only).

    Derived in-memory from the same single repository-history parse used by
    compute_change_history. contributor_count and dominant_contributor_share
    only. No organizational ownership inference.
    """
    if not repo_local_path or not affected_path:
        return {
            "contributor_count": None,
            "dominant_contributor_share": None,
            "ownership_concentration": "UNKNOWN",
            "available": False,
            "source": "no_repo_or_path",
        }
    rel = _rel_path(affected_path)
    ctx = _build_repo_git_context(repo_local_path, commit_sha or "HEAD")
    if ctx is None or rel not in ctx.file_history:
        return {
            "contributor_count": 0,
            "dominant_contributor_share": 0.0,
            "ownership_concentration": "NOT_OBSERVED",
            "available": False,
            "source": "git_log:no_contributors",
        }

    emails = [e for (_, _, e) in ctx.file_history[rel] if e]
    if not emails:
        return {
            "contributor_count": 0,
            "dominant_contributor_share": 0.0,
            "ownership_concentration": "NOT_OBSERVED",
            "available": False,
            "source": "git_log:no_contributors",
        }

    total = len(emails)
    counts: dict[str, int] = {}
    for e in emails:
        counts[e] = counts.get(e, 0) + 1
    dominant = max(counts.values())
    share = round(dominant / total, 4)

    if share >= 0.9:
        conc = "HIGH"
    elif share >= 0.6:
        conc = "MODERATE"
    else:
        conc = "DISTRIBUTED"

    return {
        "contributor_count": len(counts),
        "dominant_contributor_share": share,
        "ownership_concentration": conc,
        "available": True,
        "source": "git_shortlog:contributor_emails",
    }


# ---------------------------------------------------------------------------
# Top-level per-finding enrichment
# ---------------------------------------------------------------------------

def extract_observed_value(finding: dict[str, Any]) -> tuple[float | None, str | None, float | None]:
    """Pull observed value + threshold from the finding's evidence text.

    The Cycle 7 findings encode magnitude in titles like
    'Large module: X (1155 lines)' or 'Module has 1155 lines'. We parse the
    largest integer from the evidence detail/title. Threshold is the
    documented 300-line large-module threshold for line-count signals.
    Returns (observed, unit, threshold).
    """
    title = finding.get("title", "") or ""
    explanation = finding.get("explanation", "") or ""
    refs = finding.get("evidence_references", []) or []
    detail_blob = " ".join(str(e.get("detail", "")) for e in refs)
    blob = f"{title} {explanation} {detail_blob}"

    import re
    # Find "(1234 lines)" or "1234 lines" or "has 1234 lines"
    nums = re.findall(r"(\d{2,6})\s*lines?", blob)
    observed = int(max(nums)) if nums else None

    threshold = None
    if observed is not None:
        threshold = float(DEFAULT_LARGE_MODULE_THRESHOLD)

    unit = "lines" if observed is not None else None
    return observed, unit, threshold


def enrich_finding(
    finding: dict[str, Any],
    ri: dict[str, Any],
    *,
    repository_identifier: str | None = None,
    commit_sha: str | None = None,
    repo_local_path: str | None = None,
) -> dict[str, Any]:
    """Return an additive enrichment dict for one finding.

    Does NOT mutate `finding`. Pure + deterministic given the same inputs.
    """
    affected = ""
    comps = finding.get("affected_components", []) or []
    if comps:
        affected = comps[0].get("component_path", "") if isinstance(comps[0], dict) else ""
    if not affected:
        # fall back to module field used by some findings
        affected = finding.get("module", "") or ""

    # A. Source magnitude
    observed, unit, threshold = extract_observed_value(finding)
    magnitude = compute_exceedance(observed, threshold)
    magnitude["unit"] = unit
    magnitude["signal"] = "source_magnitude"

    # B. File context
    ctx, ctx_src = classify_file_context(affected)

    # C. Change history (git, read-only)
    change = compute_change_history(repo_local_path, commit_sha, affected)

    # D. Ownership concentration (git, read-only)
    ownership = compute_ownership(repo_local_path, commit_sha, affected)

    # E. Structural importance (RI module graph)
    structural = compute_structural_importance(ri, affected)

    # F. Evidence strength
    evidence = compute_evidence_strength(finding)

    enrichment = {
        "version": ENRICHMENT_VERSION,
        "repository_identifier": repository_identifier,
        "commit_sha": commit_sha,
        "affected_path": affected,
        "file_context": {
            "context": ctx,
            "classification": ctx,
            "source": ctx_src,
            "available": ctx != "UNKNOWN",
        },
        "source_magnitude": magnitude,
        "change_history": change,
        "ownership_concentration": ownership,
        "structural_importance": structural,
        "evidence_strength": evidence,
        # explicit: no behavioral/runtime evidence is ever claimed
        "behavioral_evidence": {
            "value": "NOT_OBSERVED",
            "available": False,
            "source": "policy:no_runtime_inference",
        },
    }
    return enrichment


def enrich_findings(
    findings: list[dict[str, Any]],
    ri: dict[str, Any],
    *,
    repository_identifier: str | None = None,
    commit_sha: str | None = None,
    repo_local_path: str | None = None,
) -> list[dict[str, Any]]:
    """Attach an `enrichment` block to each finding dict (additive).

    Returns new dicts; does not mutate inputs.
    """
    out = []
    for f in findings:
        f = dict(f)  # shallow copy
        f["enrichment"] = enrich_finding(
            f, ri,
            repository_identifier=repository_identifier,
            commit_sha=commit_sha,
            repo_local_path=repo_local_path,
        )
        out.append(f)
    return out
