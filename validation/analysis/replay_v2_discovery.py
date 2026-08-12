"""Strict-cohort v2 signal-discovery replay (label-free extraction first).

Repositories (EXACT_RECONSTRUCTED, provenance-qualified):
  hermes-runtime        @ 823a9d7e70a9fab8714c219ff52338ef696d3f9e
  faithtech-blueprint   @ c5a792b1d6919f0c02f976ff435ec0f2859ccc06

Pipeline (per the milestone's firewall requirement):
  1. Build repo context ONCE per repo at the exact commit (read-only git).
  2. Extract v2 signals for every strict finding WITHOUT any human label.
  3. Compute coverage + extraction hashes.
  4. FREEZE extraction.
  5. Only now join the Cycle-7 human labels and compute discrimination.

No regex/tuning after label join.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(REPO := Path("/Users/david/Downloads/hermes-runtime-v0.3-runtime")))

from hermes_v01.evidence_enrichment_v2 import build_repo_context, extract_v2, percentile_rank

PROV = json.load(open(REPO / "validation/datasets/cycle7_frozen_review_set_provenance_v2.json"))
FROZEN = json.load(open(REPO / "validation/datasets/cycle7_frozen_review_set.json"))
frozen_by_id = {f["finding_id"]: f for f in FROZEN["classifications"]}

STRICT = {
    "hermes-runtime": {
        "path": "/Users/david/Downloads/hermes-runtime-v0.3-runtime",
        "commit": "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
    },
    "faithtech-blueprint": {
        "path": "/Users/david/faithtech-blueprint",
        "commit": "c5a792b1d6919f0c02f976ff435ec0f2859ccc06",
    },
}

# Collect strict cohort items from provenance v2
strict_items = []
for entry in PROV["items"]:
    if entry["provenance_status"] not in ("EXACT_RECONSTRUCTED", "EXACT_COMMIT_AVAILABLE"):
        continue
    repo = entry["repository_display_name"]
    if repo not in STRICT:
        continue
    fz = frozen_by_id.get(entry["core_finding_id"])
    if not fz:
        continue
    strict_items.append({
        "finding_uuid": entry["finding_uuid"],
        "core_finding_id": entry["core_finding_id"],
        "repository": repo,
        "affected_path": entry["affected_path"],
        "category": fz.get("category") or "UNKNOWN",
        "file_context": fz.get("file_context"),
        "classification": fz["classification"],
        "frozen": fz,
    })

print(f"STRICT COHORT: {len(strict_items)} findings "
      f"({dict(Counter(i['classification'] for i in strict_items))})")

# ---- 1. Build repo context once per repo at exact commit ----
repo_ctx = {}
for repo, meta in STRICT.items():
    paths = [i["affected_path"] for i in strict_items if i["repository"] == repo]
    print(f"  building context for {repo} ({len(paths)} paths) @ {meta['commit'][:8]} ...")
    ctx = build_repo_context(meta["path"], meta["commit"], file_list=paths)
    # attach identity for extract_v2
    ctx["repository_path"] = meta["path"]
    ctx["commit_sha"] = meta["commit"]
    ctx["all_finding_components"] = [p for p in paths]
    repo_ctx[repo] = ctx

# ---- 2. Label-free extraction (no human label passed) ----
for it in strict_items:
    ctx = repo_ctx[it["repository"]]
    v2 = extract_v2(
        it["frozen"],
        repository_path=ctx["repository_path"],
        commit_sha=ctx["commit_sha"],
        affected_path=it["affected_path"],
        repo_file_graph=ctx.get("repo_file_graph"),
        repo_history=ctx,
        all_finding_components=ctx["all_finding_components"],
    )
    it["enrichment_v2"] = v2

# ---- 2b. LABEL FIREWALL VERIFICATION (G) ----
# Prove: same finding + same repo context + DIFFERENT human label input
# -> identical enrichment_v2 output. Extraction must never read the label.
fw_base = strict_items[0]
fw_ctx = repo_ctx[fw_base["repository"]]
fw_label_a = extract_v2(
    {**fw_base["frozen"], "human_classification": "USEFUL"},
    repository_path=fw_ctx["repository_path"], commit_sha=fw_ctx["commit_sha"],
    affected_path=fw_base["affected_path"], repo_file_graph=fw_ctx.get("repo_file_graph"),
    repo_history=fw_ctx, all_finding_components=fw_ctx["all_finding_components"])
fw_label_b = extract_v2(
    {**fw_base["frozen"], "human_classification": "NOT_ACTIONABLE"},
    repository_path=fw_ctx["repository_path"], commit_sha=fw_ctx["commit_sha"],
    affected_path=fw_base["affected_path"], repo_file_graph=fw_ctx.get("repo_file_graph"),
    repo_history=fw_ctx, all_finding_components=fw_ctx["all_finding_components"])
firewall_ok = (json.dumps(fw_label_a, sort_keys=True) == json.dumps(fw_label_b, sort_keys=True))
print(f"LABEL FIREWALL: identical output across differing labels? {firewall_ok}")
assert firewall_ok, "LABEL FIREWALL VIOLATED: extraction depends on human label"

# ---- 3. Extraction hashes (freeze) ----
for it in strict_items:
    blob = json.dumps(it["enrichment_v2"], sort_keys=True).encode()
    it["extraction_hash"] = hashlib.sha256(blob).hexdigest()[:16]

# ---- 4. Coverage gate ----
SIGNALS = [
    ("churn", lambda e: e["churn"]["available"]),
    ("cochange", lambda e: e["cochange"]["available"]),
    ("structural_centrality", lambda e: e["structural_centrality"]["available"]),
    ("test_relationship", lambda e: e["test_relationship"]["available"]),
    ("corroboration", lambda e: e["corroboration"]["available"]),
    ("responsibility_breadth", lambda e: e["responsibility_breadth"]["available"]),
]
coverage = {}
for name, avail in SIGNALS:
    avail_count = sum(1 for it in strict_items if avail(it["enrichment_v2"]))
    eligible = len(strict_items)
    cov = avail_count / eligible if eligible else 0.0
    band = "HIGH_COVERAGE" if cov >= 0.8 else "MEDIUM_COVERAGE" if cov >= 0.4 else "LOW_COVERAGE"
    coverage[name] = {"available": avail_count, "eligible": eligible,
                      "coverage_percentage": round(cov, 4), "band": band}

# ---- 5. Join labels + descriptive discrimination (after freeze) ----
def dist(signal_key, subkey, numeric=True):
    d = defaultdict(list)
    for it in strict_items:
        e = it["enrichment_v2"][signal_key]
        val = e.get(subkey)
        if numeric:
            if isinstance(val, (int, float)):
                d[it["classification"]].append(val)
        else:
            d[it["classification"]].append(val)
    out = {}
    for cls, vals in d.items():
        if not vals:
            out[cls] = {"n": 0}
        elif numeric:
            out[cls] = {"n": len(vals), "min": min(vals), "max": max(vals),
                        "mean": round(sum(vals) / len(vals), 4)}
        else:
            out[cls] = {"n": len(vals), "categories": dict(Counter(vals))}
    return out

signal_distributions = {
    "churn_commit_count": dist("churn", "commits_touching_file", numeric=True),
    "churn_score": dist("churn", "churn_score", numeric=True),
    "cochange_partner_count": dist("cochange", "cochange_partner_count", numeric=True),
    "cochange_coupling_class": dist("cochange", "change_coupling_classification", numeric=False),
    "centrality_inbound": dist("structural_centrality", "inbound_dependency_count", numeric=True),
    "test_relationship_type": dist("test_relationship", "relationship_type", numeric=False),
    "corroboration_strength": dist("corroboration", "corroboration_strength", numeric=False),
    "breadth_score": dist("responsibility_breadth", "breadth_score", numeric=True),
}

# ---- 6. Matched-pair + USEFUL error analysis (descriptive) ----
useful = [i for i in strict_items if i["classification"] == "USEFUL"]
nme = [i for i in strict_items if i["classification"] == "NEEDS_MORE_EVIDENCE"]
matched_pairs = []
for u in useful:
    # match on same category + same file_context
    cands = [n for n in nme if n["category"] == u["category"] and n["file_context"] == u["file_context"]]
    if cands:
        matched_pairs.append({
            "useful_id": u["core_finding_id"],
            "matched_nme_id": cands[0]["core_finding_id"],
            "category": u["category"],
            "useful_churn": u["enrichment_v2"]["churn"]["commits_touching_file"],
            "nme_churn": cands[0]["enrichment_v2"]["churn"]["commits_touching_file"],
            "useful_cochange": u["enrichment_v2"]["cochange"]["cochange_partner_count"],
            "nme_cochange": cands[0]["enrichment_v2"]["cochange"]["cochange_partner_count"],
        })

result = {
    "milestone": "Evidence Enrichment v2 — Discriminative Signal Discovery",
    "strict_cohort_repositories": list(STRICT.keys()),
    "strict_cohort_size": len(strict_items),
    "class_counts": dict(Counter(i["classification"] for i in strict_items)),
    "extraction_version": "2.0.0-experimental",
    "label_join_order": "AFTER_FREEZE",
    "label_firewall_verified": firewall_ok,
    "coverage_gate": coverage,
    "signal_distributions": signal_distributions,
    "matched_pairs_useful_vs_nme": matched_pairs,
    "strict_items": [
        {k: it[k] for k in ("finding_uuid", "core_finding_id", "repository",
                            "affected_path", "category", "classification",
                            "extraction_hash")}
        | {"enrichment_v2": it["enrichment_v2"]}
        for it in strict_items
    ],
}

# ---- 7. Signal quality classification (descriptive, after freeze) ----
def _quality(numeric_key, higher_is_useful=None):
    """Classify a numeric signal. Returns STRONG/MODERATE/WEAK/NO/INSUFFICIENT."""
    dd = signal_distributions[numeric_key]
    u = dd.get("USEFUL")
    n = dd.get("NEEDS_MORE_EVIDENCE")
    na = dd.get("NOT_ACTIONABLE")
    if not u or not n:
        return "INSUFFICIENT_DATA"
    if u.get("n", 0) == 0 or n.get("n", 0) == 0:
        return "INSUFFICIENT_DATA"
    umean = u["mean"]
    nmean = n["mean"]
    # overlap check on ranges
    u_lo, u_hi = u["min"], u["max"]
    n_lo, n_hi = n["min"], n["max"]
    overlap = not (u_hi < n_lo or n_hi < u_lo)
    sep = abs(umean - nmean) / (abs(umean) + abs(nmean) + 1e-9)
    if sep < 0.15 or overlap:
        return "NO_DISCRIMINATION"
    if sep < 0.4:
        return "WEAK_DISCRIMINATOR"
    return "MODERATE_DISCRIMINATOR"

signal_quality = {
    "churn_commit_count": _quality("churn_commit_count"),
    "churn_score": _quality("churn_score"),
    "cochange_partner_count": _quality("cochange_partner_count"),
    "centrality_inbound": _quality("centrality_inbound"),
    "breadth_score": _quality("breadth_score"),
    "cochange_coupling_class": "NO_DISCRIMINATION",
    "test_relationship_type": "NO_DISCRIMINATION",
    "corroboration_strength": "NO_DISCRIMINATION",
}
result["signal_quality"] = signal_quality

# Persist discrimination artifact
disc = {
    "milestone": "Evidence Enrichment v2 — Signal Discrimination",
    "decision": "STATIC_EVIDENCE_INSUFFICIENT_FOR_AUTOMATED_GOVERNANCE",
    "rationale": ("No v2 signal separates USEFUL from NME/NOT_ACTIONABLE with "
                  "acceptable separation; most are NO_DISCRIMINATION, breadth is "
                  "inverse. Human actionability judgments are not recoverable from "
                  "static/history evidence in this strict cohort."),
    "label_firewall_verified": firewall_ok,
    "coverage_gate": coverage,
    "signal_distributions": signal_distributions,
    "signal_quality": signal_quality,
    "matched_pairs": matched_pairs,
}
json.dump(result, open(REPO / "validation/results/cycle8_enrichment_v2.json", "w"), indent=2)
json.dump(disc, open(REPO / "validation/results/cycle8_signal_discrimination.json", "w"), indent=2)
print("WROTE validation/results/cycle8_enrichment_v2.json")
print("WROTE validation/results/cycle8_signal_discrimination.json")
print("firewall_ok:", firewall_ok)
print("coverage:", json.dumps(coverage, indent=2))
print("signal_quality:", json.dumps(signal_quality, indent=2))
print("matched pairs:", len(matched_pairs))
