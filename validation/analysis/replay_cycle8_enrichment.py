"""Replay the strict Cycle 7 cohort with Evidence Enrichment v1.

Strict cohort (provenance EXACT_RECONSTRUCTED):
  - hermes-runtime @ 823a9d7e70a9fab8714c219ff52338ef696d3f9e
  - faithtech-blueprint @ c5a792b1d6919f0c02f976ff435ec0f2859ccc06

Frozen human labels are PRESERVED (not reclassified). Enrichment is computed
read-only at the exact historical commit via git history.

Outputs validation/results/cycle8_enrichment_analysis.json
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from hermes_v01.evidence_enrichment import enrich_finding

REPO = Path("/Users/david/Downloads/hermes-runtime-v0.3-runtime")
DS = json.load(open(REPO / "validation/datasets/cycle7_frozen_review_set.json"))

STRICT = {
    "hermes-runtime": {
        "commit": "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
        "path": "/Users/david/Downloads/hermes-runtime-v0.3-runtime",
        "identifier": "Dphoshoba/hermes-runtime",
    },
    "faithtech-blueprint": {
        "commit": "c5a792b1d6919f0c02f976ff435ec0f2859ccc06",
        "path": "/Users/david/faithtech-blueprint",
        "identifier": "Dphoshoba/Faithtech-Blueprint",
    },
}

EXPLORATORY = {
    "inspirevoice-backend": {
        "commit": "83f1c00959c728fb9ee59648c2af85d459c4c6b4",
        "path": "/Users/david/inspirevoice-backend",
        "identifier": "Dphoshoba/inspirevoice-backend",
        "note": "PARTIALLY_RECONSTRUCTED — frozen paths are renamed; actual baseline path Frontend/src/App.js",
    },
    "cognikid_app": {
        "commit": "ccd1fd51f84a28fab3ce90b302601f07fc875b16",
        "path": "/Users/david/cognikid_app",
        "identifier": "Dphoshoba/CogniKid_App",
        "note": "COMMIT_UNKNOWN — candidate commit only; exact Cycle7 commit unproven",
    },
}


def observed_from_finding(c: dict) -> tuple[float | None, str | None]:
    """Extract observed line-count magnitude from a frozen Cycle7 finding."""
    blob = f"{c.get('title','')} {c.get('rationale','')} {c.get('explanation','')}"
    nums = re.findall(r"\((\d{2,6})\s*lines\)", blob)
    if nums:
        return int(nums[0]), "lines"
    nums2 = re.findall(r"(\d{2,6})\s*lines", blob)
    if nums2:
        return int(nums2[0]), "lines"
    return None, None


def enrich_strict_item(c: dict) -> dict:
    repo = c["repository"]
    meta = STRICT.get(repo) or EXPLORATORY[repo]
    affected = c.get("module", "")
    observed, unit = observed_from_finding(c)

    # Build a minimal finding dict for enrichment
    finding_like = {
        "finding_id": c["finding_id"],
        "category": "Replay",
        "severity": c.get("severity", "low"),
        "confidence": 0.5,
        "title": c.get("title", ""),
        "explanation": c.get("rationale", "") or "",
        "evidence_references": [{"source": "frozen_cycle7", "reference_path": affected,
                                  "detail": c.get("title", "")}],
        "affected_components": [{"component_type": "module",
                                  "component_path": affected,
                                  "component_name": affected.rsplit("/", 1)[-1]}],
    }
    ri = {"module_graph": {"nodes": [], "edges": []}}
    enr = enrich_finding(
        finding_like, ri,
        repository_identifier=meta["identifier"],
        commit_sha=meta["commit"],
        repo_local_path=meta["path"],
    )
    # Override magnitude observed from frozen label (richer than pattern parse)
    if observed is not None:
        enr["source_magnitude"]["observed_value"] = observed
        enr["source_magnitude"]["threshold_value"] = 300.0
        enr["source_magnitude"]["exceedance_ratio"] = round(observed / 300.0, 4)
        ratio = observed / 300.0
        tier = "LOW"
        for tname, tval in [("EXTREME", 3.0), ("HIGH", 2.0), ("MODERATE", 1.5), ("NOTABLE", 1.2), ("LOW", 1.0)]:
            if ratio >= tval:
                tier = tname
                break
        enr["source_magnitude"]["exceedance_tier"] = tier
        enr["source_magnitude"]["available"] = True
        enr["source_magnitude"]["unit"] = unit

    return {
        "finding_id": c["finding_id"],
        "repository": repo,
        "classification": c["classification"],
        "affected_path": affected,
        "file_context": c.get("file_context"),
        "enrichment": enr,
    }


def main():
    strict_items = [enrich_strict_item(c) for c in DS["classifications"]
                    if c["repository"] in STRICT]
    exploratory_items = [enrich_strict_item(c) for c in DS["classifications"]
                         if c["repository"] in EXPLORATORY]

    # ---- Discrimination analysis (strict cohort only) ----
    def signal_dist(items, key_fn, numeric=True):
        dist = defaultdict(list)
        for it in items:
            cls = it["classification"]
            dist[cls].append(key_fn(it["enrichment"]))
        if numeric:
            return {k: _summarize(v) for k, v in dist.items()}
        # categorical: return value counts per class
        result = {}
        for k, vals in dist.items():
            counts = Counter(vals)
            result[k] = {"n": len(vals), "categories": dict(counts)}
        return result

    def _summarize(vals):
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"n": 0, "min": None, "max": None, "mean": None}
        return {"n": len(vals), "min": min(vals), "max": max(vals),
                "mean": round(sum(vals) / len(vals), 4)}

    signals = {}
    signals["exceedance_ratio"] = signal_dist(
        strict_items, lambda e: e["source_magnitude"].get("exceedance_ratio"))
    signals["file_context_enum"] = signal_dist(
        strict_items, lambda e: None, numeric=False)  # placeholder replaced below
    # file_context comes from the frozen label on the item, not the enrichment dict
    _fc_dist = defaultdict(list)
    for it in strict_items:
        _fc_dist[it["classification"]].append(it["file_context"])
    signals["file_context_enum"] = {k: {"n": len(v), "categories": dict(Counter(v))} for k, v in _fc_dist.items()}
    signals["change_history_churn"] = signal_dist(
        strict_items, lambda e: e["change_history"]["churn_classification"], numeric=False)
    signals["ownership_concentration"] = signal_dist(
        strict_items, lambda e: e["ownership_concentration"]["ownership_concentration"], numeric=False)
    signals["structural_centrality"] = signal_dist(
        strict_items, lambda e: e["structural_importance"]["centrality_classification"], numeric=False)
    signals["evidence_strength"] = signal_dist(
        strict_items, lambda e: e["evidence_strength"]["evidence_strength"], numeric=False)

    # ---- Signal quality classification ----
    def classify(name, dist):
        useful = dist.get("USEFUL", {})
        if useful.get("n", 0) == 0:
            return "INSUFFICIENT_DATA"
        # Numeric signals (exceedance_ratio) carry 'mean'
        if "mean" in useful:
            nme = dist.get("NEEDS_MORE_EVIDENCE", {})
            na = dist.get("NOT_ACTIONABLE", {})
            means = [d.get("mean") for d in (useful, nme, na) if d.get("mean") is not None]
            if means and (max(means) - min(means)) / (max(means) or 1) > 0.3:
                return "MODERATE_DISCRIMINATOR"
            return "WEAK_DISCRIMINATOR"
        # Categorical signals carry 'categories' (value counts)
        useful_cats = set(useful.get("categories", {}).keys())
        other_cats = set()
        for cls in ("NEEDS_MORE_EVIDENCE", "NOT_ACTIONABLE"):
            other_cats |= set(dist.get(cls, {}).get("categories", {}).keys())
        # Strong if USEFUL occupies buckets not shared by others
        unique_to_useful = useful_cats - other_cats
        if unique_to_useful and len(unique_to_useful) == len(useful_cats):
            return "MODERATE_DISCRIMINATOR"
        return "WEAK_DISCRIMINATOR"

    quality = {name: classify(name, dist) for name, dist in signals.items()}

    # ---- Missing-data coverage ----
    coverage = {}
    for name in ["change_history", "ownership_concentration", "structural_importance",
                 "source_magnitude", "file_context", "evidence_strength"]:
        getter = {
            "change_history": lambda e: e["change_history"]["available"],
            "ownership_concentration": lambda e: e["ownership_concentration"]["available"],
            "structural_importance": lambda e: e["structural_importance"]["available"],
            "source_magnitude": lambda e: e["source_magnitude"]["available"],
            "file_context": lambda e: e["file_context"] is not None,
            "evidence_strength": lambda e: e["evidence_strength"]["available"],
        }[name]
        avail = sum(1 for it in strict_items if getter(it["enrichment"]))
        coverage[name] = {"available": avail, "eligible": len(strict_items),
                           "coverage": round(avail / len(strict_items), 4)}

    out = {
        "milestone": "Evidence Enrichment v1 — Strict Cohort Replay",
        "strict_cohort": STRICT,
        "exploratory_cohort": {k: v["note"] for k, v in EXPLORATORY.items()},
        "strict_item_count": len(strict_items),
        "exploratory_item_count": len(exploratory_items),
        "class_counts_strict": dict(Counter(it["classification"] for it in strict_items)),
        "signal_distributions": signals,
        "signal_quality": quality,
        "missing_data_coverage": coverage,
        "strict_items": strict_items,
        "exploratory_items": exploratory_items,
    }
    (REPO / "validation/results/cycle8_enrichment_analysis.json").write_text(json.dumps(out, indent=2))
    print("WROTE validation/results/cycle8_enrichment_analysis.json")
    print("strict items:", len(strict_items), "classes:", out["class_counts_strict"])
    print("signal quality:", json.dumps(quality, indent=2))
    print("coverage:", json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
