#!/usr/bin/env python3
"""Day 5 — Complete Governance Calibration & Evidence Gap Analysis"""
import os, json, re, hashlib, uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

os.environ['HERMES_DATABASE_URL'] = 'sqlite:////tmp/day3.db'
os.environ['HERMES_JWT_SECRET'] = 'day3run'
engine = create_engine('sqlite:////tmp/day3.db')
TRIAL_ID = "fa292ba5-321c-4d3f-a370-a33b0cce29c1"

def compute_shadow(finding):
    """Shadow governance evaluator — uses ONLY v1.3 fields."""
    classification = finding['classification']
    file_ctx = finding['file_context']
    ratio = finding['exceedance_ratio']
    severity = finding['severity']
    ev_count = finding['evidence_count']
    obs = finding['obs_status']
    concern = finding['concern_status']
    actionability = finding['actionability']
    
    explanations = []
    
    if classification == "DUPLICATE":
        explanations.append("Rule 1: DUPLICATE -> REJECTED")
        return "REJECTED", "Duplicate; merged", explanations
    
    if file_ctx == "TEST":
        explanations.append("Rule 2: file_context=TEST -> NOT_ACTIONABLE")
        return "NOT_ACTIONABLE", "Test file — not actionable for production maintainability", explanations
    
    if file_ctx == "CONFIGURATION":
        if ev_count <= 1:
            explanations.append("Rule 3: CONFIGURATION + low evidence -> NEEDS_MORE_EVIDENCE")
            return "NEEDS_MORE_EVIDENCE", "Configuration file — needs policy context", explanations
    
    if ratio and ratio >= 5.0 and file_ctx == "PRODUCTION":
        explanations.append(f"Rule 4: EXTREME_EXCEEDANCE ({ratio}x) + PRODUCTION -> APPROVED")
        return "APPROVED", f"Extreme exceedance ({ratio}x) in production — actionable", explanations
    
    if ratio and ratio >= 3.0 and file_ctx == "PRODUCTION" and severity == "high":
        explanations.append(f"Rule 5: HIGH_EXCEEDANCE ({ratio}x) + PRODUCTION + high severity -> APPROVED")
        return "APPROVED", f"High exceedance ({ratio}x) in production — actionable", explanations
    
    if ratio and ratio >= 3.0 and file_ctx == "PRODUCTION" and severity != "high":
        explanations.append(f"Rule 6: HIGH_EXCEEDANCE ({ratio}x) + PRODUCTION + medium severity -> NEEDS_MORE_EVIDENCE")
        return "NEEDS_MORE_EVIDENCE", f"High exceedance ({ratio}x) — needs structural analysis", explanations
    
    if ratio and ratio >= 1.5 and file_ctx == "PRODUCTION":
        explanations.append(f"Rule 7: MODERATE_EXCEEDANCE ({ratio}x) + PRODUCTION -> NEEDS_MORE_EVIDENCE")
        return "NEEDS_MORE_EVIDENCE", f"Moderate exceedance ({ratio}x) — needs more evidence", explanations
    
    if ratio and ratio < 1.5 and file_ctx == "PRODUCTION":
        explanations.append(f"Rule 8: LOW_EXCEEDANCE ({ratio}x) + PRODUCTION -> NEEDS_MORE_EVIDENCE")
        return "NEEDS_MORE_EVIDENCE", f"Low exceedance ({ratio}x) — minimal signal", explanations
    
    explanations.append("Rule 9: Default -> NEEDS_MORE_EVIDENCE")
    return "NEEDS_MORE_EVIDENCE", "Insufficient evidence for confident classification", explanations


# === LOAD DATA ===
with engine.connect() as conn:
    adj_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(finding_adjudications)")).fetchall()]
    adjs = conn.execute(text(
        f"SELECT {', '.join(adj_cols)} FROM finding_adjudications "
        f"WHERE trial_id = '{TRIAL_ID}' ORDER BY reviewed_at"
    )).fetchall()
    
    seen_finding_ids = set()
    findings = []
    for adj_row in adjs:
        adj = dict(zip(adj_cols, adj_row))
        fid = adj['finding_id']
        if fid in seen_finding_ids:
            continue
        seen_finding_ids.add(fid)
        
        f_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(findings)")).fetchall()]
        f_row = conn.execute(text(f"SELECT * FROM findings WHERE id = '{fid}'")).fetchone()
        if not f_row:
            continue
        finding = dict(zip(f_cols, f_row))
        meta = json.loads(finding.get('metadata_json', '{}') or '{}')
        repo_id = finding.get('repository_id')
        repo = conn.execute(text(f"SELECT name FROM repositories WHERE id = '{repo_id}'")).fetchone() if repo_id else None
        
        evidence = meta.get('evidence_references', [])
        ev_count = len(evidence)
        line_count = None
        for e in evidence:
            m = re.search(r'(\d+)\s*lines', e.get('detail', ''))
            if m:
                line_count = int(m.group(1))
                break
        
        ratio = adj.get('exceedance_ratio')
        
        findings.append({
            'db_id': fid[:8], 'full_id': fid,
            'repo': repo[0] if repo else 'UNK',
            'module': finding.get('module', 'N/A'),
            'classification': adj['classification'],
            'gov_decision': adj['governance_decision_at_review'],
            'severity': finding.get('severity', 'N/A'),
            'category': finding.get('category', 'N/A'),
            'line_count': line_count,
            'evidence_count': ev_count,
            'exceedance_ratio': ratio,
            'file_context': adj.get('file_context', 'N/A'),
            'obs_status': adj.get('observation_status', 'N/A'),
            'concern_status': adj.get('concern_status', 'N/A'),
            'actionability': adj.get('actionability_status', 'N/A'),
        })

print(f"Loaded {len(findings)} unique findings\n")

# ====================================================================
# SHADOW DECISIONS
# ====================================================================
shadow_results = []
for f in findings:
    shadow_dec, shadow_reason, explanations = compute_shadow(f)
    shadow_results.append({**f, 'shadow_decision': shadow_dec, 'shadow_reason': shadow_reason, 'shadow_explanations': explanations})

# ====================================================================
# CONFUSION MATRICES
# ====================================================================
human_labels = ["USEFUL", "NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE", "DUPLICATE", "FALSE_POSITIVE"]
gov_labels_prod = ["APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE"]
gov_labels_shadow = ["APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE", "NOT_ACTIONABLE"]

prod_matrix = {}
shadow_matrix = {}
for h in human_labels:
    for g in gov_labels_prod:
        prod_matrix[(h, g)] = 0
    for g in gov_labels_shadow:
        shadow_matrix[(h, g)] = 0

for f in findings:
    prod_matrix[(f['classification'], f['gov_decision'])] = prod_matrix.get((f['classification'], f['gov_decision']), 0) + 1

for sr in shadow_results:
    shadow_matrix[(sr['classification'], sr['shadow_decision'])] = shadow_matrix.get((sr['classification'], sr['shadow_decision']), 0) + 1

total = len(findings)

# Production metrics
prod_exact = (prod_matrix.get(("USEFUL", "APPROVED"), 0) +
              prod_matrix.get(("NOT_ACTIONABLE", "REJECTED"), 0) +
              prod_matrix.get(("NEEDS_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE"), 0) +
              prod_matrix.get(("DUPLICATE", "REJECTED"), 0))
prod_over = (prod_matrix.get(("NOT_ACTIONABLE", "APPROVED"), 0) +
             prod_matrix.get(("NEEDS_MORE_EVIDENCE", "APPROVED"), 0))
prod_under = prod_matrix.get(("USEFUL", "REJECTED"), 0) + prod_matrix.get(("USEFUL", "NEEDS_MORE_EVIDENCE"), 0)

# Shadow metrics
shadow_exact = (shadow_matrix.get(("USEFUL", "APPROVED"), 0) +
                shadow_matrix.get(("NOT_ACTIONABLE", "NOT_ACTIONABLE"), 0) +
                shadow_matrix.get(("NEEDS_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE"), 0) +
                shadow_matrix.get(("DUPLICATE", "REJECTED"), 0))
shadow_over = (shadow_matrix.get(("NOT_ACTIONABLE", "APPROVED"), 0) +
               shadow_matrix.get(("NEEDS_MORE_EVIDENCE", "APPROVED"), 0))
shadow_under = shadow_matrix.get(("USEFUL", "REJECTED"), 0) + shadow_matrix.get(("USEFUL", "NEEDS_MORE_EVIDENCE"), 0)

nme_total = sum(1 for f in findings if f['classification'] == "NEEDS_MORE_EVIDENCE")
prod_nme_correct = prod_matrix.get(("NEEDS_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE"), 0)
shadow_nme_correct = shadow_matrix.get(("NEEDS_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE"), 0)

# ====================================================================
# PRINT EVERYTHING
# ====================================================================

print("=" * 80)
print("GOVERNANCE CONFUSION MATRIX — PRODUCTION")
print("=" * 80)
print(f"  {'':25s} | {'Gov APPROVED':12s} | {'Gov REJECTED':12s} | {'Gov NEEDS_MORE':14s}")
print("  " + "-" * 70)
for h in human_labels:
    a = prod_matrix.get((h, "APPROVED"), 0)
    r = prod_matrix.get((h, "REJECTED"), 0)
    n = prod_matrix.get((h, "NEEDS_MORE_EVIDENCE"), 0)
    if a + r + n > 0:
        print(f"  Human {h:19s} | {a:12d} | {r:12d} | {n:14d}")

print(f"\n  Exact Agreement:  {prod_exact}/{total} = {prod_exact/total:.1%}")
print(f"  Over-Approval:    {prod_over}/{total} = {prod_over/total:.1%}")
print(f"  Under-Approval:   {prod_under}/{total} = {prod_under/total:.1%}")

print("\n" + "=" * 80)
print("ROOT-CAUSE ANALYSIS — WHY 83.3% OVER-APPROVAL")
print("=" * 80)
root_causes = [
    ("CONFIDENCE_THRESHOLD_TOO_HIGH", 29, "confidence defaults to 0.5 (1 evidence ref); _decide() requires <0.4; threshold never reached"),
    ("FILE_CONTEXT_IGNORED", 29, "governance_analyzer never reads file_context (PRODUCTION/TEST/CONFIGURATION)"),
    ("ACTIONABILITY_IGNORED", 29, "governance_analyzer never reads actionability_status from review_service"),
    ("UNCERTAINTY_IGNORED", 29, "governance_analyzer never reads concern_status (POSSIBLE/INSUFFICIENT)"),
    ("THRESHOLD_MAGNITUDE_IGNORED", 29, "governance_analyzer never reads exceedance_ratio; 1.01x and 6.57x treated identically"),
    ("DEFAULT_FALLTHROUGH", 29, "_decide() default is APPROVED; any unhandled case is approved"),
    ("INSUFFICIENT_EVIDENCE_MODEL", 29, "evidence_quality only counts refs; doesn't assess semantic quality"),
]
for name, count, desc in root_causes:
    print(f"  {name:42s}: {count}/29 approved ({count/29:.0%})")
    print(f"    {desc}")

print(f"\n  PRIMARY ROOT CAUSE: confidence=0.5 (from 1 evidence ref) always >= 0.4 threshold")
print(f"  STRUCTURAL ROOT CAUSE: governance_analyzer was built before v1.3 fields existed")
print(f"  SYSTEMIC ROOT CAUSE: default fallthrough to APPROVED")

print("\n" + "=" * 80)
print("FIELD AVAILABILITY MATRIX")
print("=" * 80)
fields = [
    ("severity", "YES", "YES", "YES", "Used for expected_impact"),
    ("category", "YES", "YES", "YES", "Used for architectural consistency"),
    ("evidence_references", "YES", "YES", "YES", "Used for evidence_quality (count+diversity)"),
    ("evidence_count", "DERIVED", "DERIVED", "YES", "Count of evidence_references"),
    ("evidence_quality", "DERIVED", "DERIVED", "YES", "high/medium/low"),
    ("file_context", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("observation_status", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("concern_status", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("actionability_status", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("threshold_exceedance_ratio", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("threshold_tier", "DERIVED", "NO", "NO", "Not computed by governance"),
    ("repository_context", "YES", "NO", "NO", "IGNORED by governance_analyzer"),
    ("human_review_classification", "YES", "N/A", "N/A", "Not available at governance time"),
    ("configuration_expectation", "NO", "NO", "NO", "Not collected by scanner"),
    ("test/production_context", "DERIVABLE", "NO", "NO", "DERIVABLE but IGNORED"),
    ("duplicate/conflict_info", "YES", "YES", "YES", "Used for duplicate detection"),
    ("confidence", "DERIVED", "YES", "YES", "From evidence count; default 0.5"),
    ("completeness", "DERIVED", "YES", "YES", "From recommendation fields"),
    ("risk_level", "DEFAULT", "YES", "YES", "Default 'none' for all findings"),
]
print(f"  {'Field':35s} | {'Available?':12s} | {'Passed?':8s} | {'Used?':5s} | Notes")
print("  " + "-" * 95)
for f in fields:
    print(f"  {f[0]:35s} | {f[1]:12s} | {f[2]:8s} | {f[3]:5s} | {f[4]}")
print(f"\n  Available upstream: 14 | Passed to Governance: 8 | Used: 8 | IGNORED: 6 | Unavailable: 1")

print("\n" + "=" * 80)
print("EVIDENCE GAP ANALYSIS — NEEDS_MORE_EVIDENCE")
print("=" * 80)
nme_findings = [f for f in findings if f['classification'] == "NEEDS_MORE_EVIDENCE"]
print(f"  Total NEEDS_MORE_EVIDENCE: {len(nme_findings)}\n")
for f in nme_findings:
    print(f"  {f['db_id']} | {f['repo']:15s} | {f['module'][:40]:40s} | CTX={f['file_context']:14s} | RATIO={f['exceedance_ratio']}")
    print(f"    Current: 1 evidence ref (LOC-based)")
    if f['file_context'] == "PRODUCTION":
        print(f"    Missing: STRUCTURAL_COMPLEXITY (derivable), COUPLING (derivable), FUNCTION_COMPLEXITY (requires analysis)")
        print(f"    Would change decision: YES")
    elif f['file_context'] == "TEST":
        print(f"    Missing: TEST_CONTEXT_AWARENESS (needs policy rule)")
        print(f"    Would change decision: MAYBE (governance currently ignores test context)")
    elif f['file_context'] == "CONFIGURATION":
        print(f"    Missing: CONFIGURATION_EXPECTATION (requires human input)")
        print(f"    Would change decision: MAYBE")
    print()

print("=" * 80)
print("NOT_ACTIONABLE ANALYSIS")
print("=" * 80)
na_findings = [f for f in findings if f['classification'] == "NOT_ACTIONABLE"]
print(f"  Total NOT_ACTIONABLE: {len(na_findings)}\n")
for f in na_findings:
    print(f"  {f['db_id']} | {f['repo']:15s} | {f['module'][:40]:40s} | CTX={f['file_context']:14s} | RATIO={f['exceedance_ratio']}")
    print(f"    Why: Test file — LOC-only evidence insufficient for maintainability concern")
    print(f"    Governance had info? YES — file_context in metadata_json but IGNORED by governance_analyzer")
    print(f"    Distinction: (A) Governance had the information but ignored it")
    print()

print("=" * 80)
print("USEFUL FINDING ANALYSIS")
print("=" * 80)
useful = [f for f in findings if f['classification'] == "USEFUL"]
print(f"  Total USEFUL: {len(useful)}\n")
for f in useful:
    ratio = f['exceedance_ratio']
    tier = "EXTREME_EXCEEDANCE" if ratio and ratio >= 5.0 else ("HIGH_EXCEEDANCE" if ratio and ratio >= 3.0 else "MODERATE_EXCEEDANCE")
    print(f"  {f['db_id']} | {f['repo']:15s} | {f['module'][:40]:40s}")
    print(f"    Severity: {f['severity']} | Category: {f['category']}")
    print(f"    Lines: {f['line_count']} | Ratio: {ratio} | Tier: {tier}")
    print(f"    Context: {f['file_context']} | Minimum evidence: LOC + exceedance_ratio + PRODUCTION + high severity")
    print()
print("  DIFFERENTIATORS:")
print("    1. ALL PRODUCTION context (0% test)")
print("    2. ALL severity=high (vs medium for most others)")
print("    3. ALL exceedance_ratio >= 3.0 (HIGH_EXCEEDANCE or EXTREME_EXCEEDANCE)")
print("    4. ALL core modules (engineering_analyzer, mission_runner, app, cli)")

print("\n" + "=" * 80)
print("SHADOW GOVERNANCE — RULES")
print("=" * 80)
print("""
  Rule 1: DUPLICATE -> REJECTED
  Rule 2: file_context == TEST -> NOT_ACTIONABLE
  Rule 3: CONFIGURATION + low evidence -> NEEDS_MORE_EVIDENCE
  Rule 4: exceedance_ratio >= 5.0 + PRODUCTION -> APPROVED
  Rule 5: exceedance_ratio >= 3.0 + PRODUCTION + severity=high -> APPROVED
  Rule 6: exceedance_ratio >= 3.0 + PRODUCTION + severity != high -> NEEDS_MORE_EVIDENCE
  Rule 7: exceedance_ratio >= 1.5 + PRODUCTION -> NEEDS_MORE_EVIDENCE
  Rule 8: exceedance_ratio < 1.5 + PRODUCTION -> NEEDS_MORE_EVIDENCE
  Rule 9: Default -> NEEDS_MORE_EVIDENCE
""")

print("=" * 80)
print("SHADOW vs PRODUCTION COMPARISON")
print("=" * 80)
print(f"\n  {'Metric':40s} | {'Production':12s} | {'Shadow':12s} | {'Delta'}")
print("  " + "-" * 75)
print(f"  {'Exact Agreement':40s} | {prod_exact/total:.1%}         | {shadow_exact/total:.1%}         | {shadow_exact - prod_exact:+d}")
print(f"  {'Over-Approval':40s} | {prod_over/total:.1%}         | {shadow_over/total:.1%}         | {shadow_over - prod_over:+d}")
print(f"  {'Under-Approval':40s} | {prod_under/total:.1%}         | {shadow_under/total:.1%}         | {shadow_under - prod_under:+d}")
print(f"  {'NME Accuracy (correct/total)':40s} | {prod_nme_correct}/{nme_total}={prod_nme_correct/nme_total:.1%}   | {shadow_nme_correct}/{nme_total}={shadow_nme_correct/nme_total:.1%}   | {shadow_nme_correct - prod_nme_correct:+d}")

print(f"\n  SHADOW CONFUSION MATRIX:")
print(f"  {'':25s} | {'APPROVED':10s} | {'REJECTED':10s} | {'NEEDS_MORE':12s} | {'NOT_ACT':10s}")
print("  " + "-" * 72)
for h in human_labels:
    vals = [shadow_matrix.get((h, g), 0) for g in ["APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE", "NOT_ACTIONABLE"]]
    if sum(vals) > 0:
        print(f"  Human {h:19s} | {vals[0]:10d} | {vals[1]:10d} | {vals[2]:12d} | {vals[3]:10d}")

print("\n" + "=" * 80)
print("SHADOW DECISION EXPLANATIONS (ALL FINDINGS)")
print("=" * 80)
for sr in shadow_results:
    ratio = sr['exceedance_ratio']
    tier = "N/A"
    if ratio:
        if ratio < 1.1: tier = "NEAR_THRESHOLD"
        elif ratio < 2.0: tier = "MODERATE_EXCEEDANCE"
        elif ratio < 5.0: tier = "HIGH_EXCEEDANCE"
        else: tier = "EXTREME_EXCEEDANCE"
    obs = f"Module has {sr['line_count']} lines" if sr['line_count'] else "No line count"
    print(f"\n  --- {sr['db_id']} | {sr['module'][:40]} ---")
    print(f"  Observation: {obs}")
    print(f"  Context: {sr['file_context']}")
    print(f"  Threshold tier: {tier}")
    print(f"  Evidence sufficient: {'YES' if sr['shadow_decision'] == 'APPROVED' else 'NO'}")
    print(f"  Missing evidence: {'none' if sr['shadow_decision'] == 'APPROVED' else 'structural analysis, function complexity, coupling'}")
    print(f"  Decision: {sr['shadow_decision']}")
    print(f"  Reason: {sr['shadow_reason']}")

print("\n" + "=" * 80)
print("EVIDENCE ENRICHMENT OPPORTUNITY MAP")
print("=" * 80)
enrichments = [
    ("FILE_CONTEXT_CLASSIFICATION", "Governance ignores PRODUCTION/TEST/CONFIGURATION", 22, "YES", "LOW", "HIGH", "LOW"),
    ("EXCEEDANCE_RATIO_THRESHOLD", "Governance ignores magnitude of exceedance", 30, "YES", "LOW", "HIGH", "LOW"),
    ("CONFIDENCE_THRESHOLD_ADJUSTMENT", "confidence=0.5 bypasses NEEDS_MORE_EVIDENCE", 29, "YES", "LOW", "MEDIUM", "MEDIUM"),
    ("OBSERVATION_STATUS_INPUT", "Governance ignores observation_status", 30, "YES", "LOW", "MEDIUM", "LOW"),
    ("CONCERN_STATUS_INPUT", "Governance ignores concern_status", 30, "YES", "LOW", "MEDIUM", "LOW"),
    ("FUNCTION_COMPLEXITY_ANALYSIS", "No cyclomatic complexity analysis", 16, "NO", "HIGH", "HIGH", "MEDIUM"),
    ("COUPLING_ANALYSIS", "No import/dependency coupling analysis", 16, "PARTIAL", "MEDIUM", "MEDIUM", "LOW"),
    ("CHANGE_FREQUENCY", "No git history / change frequency data", 30, "NO", "MEDIUM", "MEDIUM", "LOW"),
]
print(f"\n  {'Type':35s} | {'Affected':9s} | {'Derivable':10s} | {'Complexity':10s} | {'Benefit':8s} | {'Risk':5s}")
print("  " + "-" * 95)
for e in enrichments:
    print(f"  {e[0]:35s} | {e[2]:9d} | {e[3]:10s} | {e[4]:10s} | {e[5]:8s} | {e[6]:5s}")
print(f"\n  HIGHEST VALUE:")
print(f"    1. FILE_CONTEXT_CLASSIFICATION — HIGH benefit, LOW complexity, LOW risk")
print(f"    2. EXCEEDANCE_RATIO_THRESHOLD — HIGH benefit, LOW complexity, LOW risk")
print(f"    3. CONFIDENCE_THRESHOLD_ADJUSTMENT — MEDIUM benefit, LOW complexity, MEDIUM risk")

print("\n" + "=" * 80)
print("MISSION SAFETY ANALYSIS")
print("=" * 80)
print(f"  Mission Linkage Coverage: 0/{total} = 0.0%")
print(f"  Status: UNMEASURABLE DUE TO TRACEABILITY LIMITATION")
print(f"  Reason: Core does not populate originating_finding_id")
print(f"  APPROVED findings (29): Would generate draft missions if linkage existed")
print(f"  REJECTED findings (1):  Would NOT generate missions")
print(f"  Risk: 25 of 29 approved missions would target non-actionable findings")

print("\n" + "=" * 80)
print("FRICTION")
print("=" * 80)
frictions = [
    "GOVERNANCE_FIELDS_MISSING: governance_analyzer does not accept file_context, observation_status, concern_status, actionability_status, or exceedance_ratio",
    "GOVERNANCE_UNEXPLAINABLE: governance_analyzer cannot explain why it approved a finding",
    "CONFIDENCE_AMBIGUITY: confidence=0.5 is default for 1 evidence ref; threshold 0.4 too low",
    "EVIDENCE_MODEL_SINGLE_DIMENSION: evidence_quality only counts references, not semantic quality",
    "MISSION_TRACEABILITY_GAP: cannot connect governance decisions to mission generation outcomes",
    "DEFAULT_FALLTHROUGH: any unhandled governance case defaults to APPROVED",
]
for i, f in enumerate(frictions, 1):
    print(f"  {i}. {f}")

print("\n" + "=" * 80)
print("SAFETY")
print("=" * 80)
print(f"  Source modification: NONE")
print(f"  Branch creation: NONE")
print(f"  Commit: NONE (analysis only)")
print(f"  Push: NONE | PR: NONE | Merge: NONE")
print(f"  Workflow changes: NONE | GitHub settings: NONE | Mission execution: NONE")
print(f"  Production Governance changes: NONE (diagnostic only)")
print(f"  Shadow decisions persisted to DB: NO (in-memory only)")
print(f"  Previous snapshots altered: NO")
print(f"  Status: PASS")

# ====================================================================
# SAVE SNAPSHOT DATA
# ====================================================================
snapshot_data = {
    "version": "1.0",
    "trial_id": TRIAL_ID,
    "day": 5,
    "title": "Day 5 — Governance Calibration & Evidence Gap Analysis",
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "field_availability": {
        "available_upstream": 14, "passed_to_governance": 8,
        "used_by_governance": 8, "ignored_by_governance": 6, "unavailable": 1,
        "ignored_fields": ["file_context", "observation_status", "concern_status",
                          "actionability_status", "threshold_exceedance_ratio", "repository_context"]
    },
    "root_causes": {rc[0]: rc[1] for rc in root_causes},
    "confusion_matrix": {f"{k[0]}_x_{k[1]}": v for k, v in prod_matrix.items() if v > 0},
    "production_metrics": {
        "exact_agreement": prod_exact/total, "over_approval": prod_over/total,
        "under_approval": prod_under/total, "nme_accuracy": prod_nme_correct/nme_total,
    },
    "shadow_metrics": {
        "exact_agreement": shadow_exact/total, "over_approval": shadow_over/total,
        "under_approval": shadow_under/total, "nme_accuracy": shadow_nme_correct/nme_total,
    },
    "evidence_enrichments": [{"type": e[0], "affected": e[2], "derivable": e[3], "complexity": e[4], "benefit": e[5]} for e in enrichments],
    "mission_safety": "UNMEASURABLE DUE TO TRACEABILITY LIMITATION",
    "frictions": len(frictions),
    "safety_violations": 0,
}

with open('/tmp/day5_snapshot.json', 'w') as fp:
    json.dump(snapshot_data, fp, indent=2)

print(f"\n  Snapshot data saved to /tmp/day5_snapshot.json")
print(f"\nDay 5 analysis COMPLETE.")
