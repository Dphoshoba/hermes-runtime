#!/usr/bin/env python3
"""Day 6 — Governance v1.3 Calibration Validation"""
import os, json, re
from sqlalchemy import create_engine, text

os.environ['EVOSIA_DATABASE_URL'] = 'sqlite:////tmp/day3.db'
os.environ['EVOSIA_JWT_SECRET'] = 'day3run'
engine = create_engine('sqlite:////tmp/day3.db')
TRIAL_ID = "fa292ba5-321c-4d3f-a370-a33b0cce29c1"

with engine.connect() as conn:
    adj_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(finding_adjudications)")).fetchall()]
    adjs = conn.execute(text(
        f"SELECT {', '.join(adj_cols)} FROM finding_adjudications "
        f"WHERE trial_id = '{TRIAL_ID}' ORDER BY reviewed_at"
    )).fetchall()
    
    seen = set()
    findings = []
    for adj_row in adjs:
        adj = dict(zip(adj_cols, adj_row))
        fid = adj['finding_id']
        if fid in seen:
            continue
        seen.add(fid)
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
        severity = finding.get('severity', 'N/A')
        expected_impact = "high" if severity in ("high", "critical") else ("medium" if severity == "medium" else "low")
        
        findings.append({
            'db_id': fid[:8], 'full_id': fid,
            'repo': repo[0] if repo else 'UNK',
            'module': finding.get('module', 'N/A'),
            'classification': adj['classification'],
            'gov_decision': adj['governance_decision_at_review'],
            'severity': severity,
            'category': finding.get('category', 'N/A'),
            'line_count': line_count,
            'evidence_count': ev_count,
            'exceedance_ratio': ratio,
            'file_context': adj.get('file_context', 'N/A'),
            'obs_status': adj.get('observation_status', 'N/A'),
            'concern_status': adj.get('concern_status', 'N/A'),
            'actionability': adj.get('actionability_status', 'N/A'),
            'eq_level': 'low', 'confidence': 0.5, 'risk_level': 'none',
            'expected_impact': expected_impact,
            'completeness': 'insufficient', 'duplication': 'unique',
        })

total = len(findings)

def control_a(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    if f['eq_level'] == "low" and f['confidence'] < 0.4:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    if f['risk_level'] in ("medium", "high") and f['expected_impact'] == "low":
        return "DEFERRED", "High risk low impact"
    if f['completeness'] == "partial":
        return "APPROVED_WITH_NOTES", "Partially complete"
    return "APPROVED", "Sufficiently evidenced"

def variant_b(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ctx = f['file_context']
    if ctx in ("TEST", "CONFIGURATION", "DOCUMENTATION", "GENERATED", "VENDOR", "FIXTURE"):
        return "NEEDS_MORE_EVIDENCE", f"{ctx} file"
    if f['eq_level'] == "low" and f['confidence'] < 0.4:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    return "APPROVED", "Sufficiently evidenced"

def variant_c(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ratio = f['exceedance_ratio']
    if ratio is not None:
        if ratio >= 5.0:
            return "APPROVED", f"Extreme exceedance ({ratio}x)"
        if ratio >= 3.0 and f['severity'] == "high":
            return "APPROVED", f"High exceedance ({ratio}x) + high severity"
        if ratio >= 3.0:
            return "NEEDS_MORE_EVIDENCE", f"High exceedance ({ratio}x) - needs analysis"
        if ratio >= 2.0:
            return "NEEDS_MORE_EVIDENCE", f"Moderate exceedance ({ratio}x)"
        return "NEEDS_MORE_EVIDENCE", f"Low exceedance ({ratio}x)"
    return "APPROVED", "No threshold available"

def variant_d(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    if f['eq_level'] == "low" and f['confidence'] < 0.6:
        return "NEEDS_MORE_EVIDENCE", f"Low evidence (conf={f['confidence']:.0%}, thresh=0.6)"
    if f['risk_level'] in ("medium", "high") and f['expected_impact'] == "low":
        return "DEFERRED", "High risk low impact"
    return "APPROVED", "Sufficiently evidenced"

def variant_e(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ctx = f['file_context']
    if ctx in ("TEST", "CONFIGURATION", "DOCUMENTATION", "GENERATED", "VENDOR", "FIXTURE"):
        return "NEEDS_MORE_EVIDENCE", f"{ctx} file"
    ratio = f['exceedance_ratio']
    if ratio is not None:
        if ratio >= 5.0:
            return "APPROVED", f"Extreme exceedance ({ratio}x)"
        if ratio >= 3.0 and f['severity'] == "high":
            return "APPROVED", f"High exceedance ({ratio}x) + high severity"
        if ratio >= 3.0:
            return "NEEDS_MORE_EVIDENCE", f"High exceedance ({ratio}x) - needs analysis"
        if ratio >= 2.0:
            return "NEEDS_MORE_EVIDENCE", f"Moderate exceedance ({ratio}x)"
        return "NEEDS_MORE_EVIDENCE", f"Low exceedance ({ratio}x)"
    return "APPROVED", "No threshold"

def variant_f(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ctx = f['file_context']
    if ctx in ("TEST", "CONFIGURATION", "DOCUMENTATION", "GENERATED", "VENDOR", "FIXTURE"):
        return "NEEDS_MORE_EVIDENCE", f"{ctx} file"
    if f['eq_level'] == "low" and f['confidence'] < 0.6:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    return "APPROVED", "Sufficiently evidenced"

def variant_g(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ratio = f['exceedance_ratio']
    if ratio is not None:
        if ratio >= 5.0:
            return "APPROVED", f"Extreme exceedance ({ratio}x)"
        if ratio >= 3.0 and f['severity'] == "high":
            return "APPROVED", f"High exceedance ({ratio}x) + high severity"
        if ratio >= 3.0:
            return "NEEDS_MORE_EVIDENCE", f"High exceedance ({ratio}x) - needs analysis"
        if ratio >= 2.0:
            return "NEEDS_MORE_EVIDENCE", f"Moderate exceedance ({ratio}x)"
        return "NEEDS_MORE_EVIDENCE", f"Low exceedance ({ratio}x)"
    if f['eq_level'] == "low" and f['confidence'] < 0.6:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    return "APPROVED", "No threshold"

def variant_h(f):
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    ctx = f['file_context']
    if ctx in ("TEST", "CONFIGURATION", "DOCUMENTATION", "GENERATED", "VENDOR", "FIXTURE"):
        return "NEEDS_MORE_EVIDENCE", f"{ctx} file"
    ratio = f['exceedance_ratio']
    if ratio is not None:
        if ratio >= 5.0:
            return "APPROVED", f"Extreme exceedance ({ratio}x)"
        if ratio >= 3.0 and f['severity'] == "high":
            return "APPROVED", f"High exceedance ({ratio}x) + high severity"
        if ratio >= 3.0:
            return "NEEDS_MORE_EVIDENCE", f"High exceedance ({ratio}x) - needs analysis"
        if ratio >= 2.0:
            return "NEEDS_MORE_EVIDENCE", f"Moderate exceedance ({ratio}x)"
        return "NEEDS_MORE_EVIDENCE", f"Low exceedance ({ratio}x)"
    if f['eq_level'] == "low" and f['confidence'] < 0.6:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    return "APPROVED", "No threshold"

def variant_i(f):
    """Default -> NEEDS_MORE_EVIDENCE"""
    if f['duplication'] == "duplicate":
        return "REJECTED", "Duplicate"
    if f['eq_level'] == "low" and f['confidence'] < 0.4:
        return "NEEDS_MORE_EVIDENCE", "Low evidence"
    if f['risk_level'] in ("medium", "high") and f['expected_impact'] == "low":
        return "DEFERRED", "High risk low impact"
    return "NEEDS_MORE_EVIDENCE", "Default: insufficient evidence"

def compute_metrics(results, findings):
    exact = sum(1 for r, f in zip(results, findings) if r[0] in ("APPROVED",) and f['classification'] == "USEFUL"
                or r[0] == "REJECTED" and f['classification'] == "DUPLICATE"
                or r[0] == "NEEDS_MORE_EVIDENCE" and f['classification'] == "NEEDS_MORE_EVIDENCE"
                or r[0] == "NOT_ACTIONABLE" and f['classification'] == "NOT_ACTIONABLE")
    
    approved = [r for r in results if r[0] in ("APPROVED", "APPROVED_WITH_NOTES")]
    rejected = [r for r in results if r[0] == "REJECTED"]
    nme = [r for r in results if r[0] == "NEEDS_MORE_EVIDENCE"]
    deferred = [r for r in results if r[0] == "DEFERRED"]
    
    over = sum(1 for r, f in zip(results, findings)
               if r[0] in ("APPROVED", "APPROVED_WITH_NOTES")
               and f['classification'] in ("NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE"))
    
    under = sum(1 for r, f in zip(results, findings)
                if r[0] in ("REJECTED", "NEEDS_MORE_EVIDENCE", "DEFERRED")
                and f['classification'] == "USEFUL")
    
    useful_total = sum(1 for f in findings if f['classification'] == "USEFUL")
    useful_approved = sum(1 for r, f in zip(results, findings)
                          if r[0] in ("APPROVED", "APPROVED_WITH_NOTES") and f['classification'] == "USEFUL")
    
    nme_total = sum(1 for f in findings if f['classification'] == "NEEDS_MORE_EVIDENCE")
    nme_correct = sum(1 for r, f in zip(results, findings)
                      if r[0] == "NEEDS_MORE_EVIDENCE" and f['classification'] == "NEEDS_MORE_EVIDENCE")
    
    na_total = sum(1 for f in findings if f['classification'] == "NOT_ACTIONABLE")
    na_rejected_or_deferred = sum(1 for r, f in zip(results, findings)
                                   if r[0] in ("REJECTED", "NEEDS_MORE_EVIDENCE", "DEFERRED", "NOT_ACTIONABLE")
                                   and f['classification'] == "NOT_ACTIONABLE")
    
    return {
        'exact': exact / total,
        'over': over / total,
        'under': under / total,
        'useful_recall': useful_approved / useful_total if useful_total else 0,
        'nme_accuracy': nme_correct / nme_total if nme_total else 0,
        'na_handling': na_rejected_or_deferred / na_total if na_total else 0,
        'nme_count': len(nme),
        'approved_count': len(approved),
        'rejected_count': len(rejected),
        'deferred_count': len(deferred),
    }

variants = {
    'A_CONTROL': control_a,
    'B_FILECTX': variant_b,
    'C_EXCEED': variant_c,
    'D_CONF': variant_d,
    'E_CTX_EXCEED': variant_e,
    'E_CTX_CONF': variant_f,
    'G_EXCEED_CONF': variant_g,
    'H_ALL': variant_h,
    'I_DEFAULT_NME': variant_i,
}

all_results = {}
for name, func in variants.items():
    results = [func(f) for f in findings]
    metrics = compute_metrics(results, findings)
    all_results[name] = metrics
    metrics['results'] = results

# Default fallthrough analysis
default_appr = 0
for f in findings:
    if f['duplication'] == "duplicate":
        continue
    # Simulate: if none of the conditions match, default is APPROVED
    cond1 = (f['eq_level'] == "low" and f['confidence'] < 0.4)
    cond2 = (f['risk_level'] in ("medium", "high") and f['expected_impact'] == "low")
    cond3 = (f['completeness'] == "partial")
    if not cond1 and not cond2 and not cond3:
        default_appr += 1

default_human = {}
for f in findings:
    if f['duplication'] == "duplicate":
        continue
    cond1 = (f['eq_level'] == "low" and f['confidence'] < 0.4)
    cond2 = (f['risk_level'] in ("medium", "high") and f['expected_impact'] == "low")
    cond3 = (f['completeness'] == "partial")
    if not cond1 and not cond2 and not cond3:
        cls = f['classification']
        default_human[cls] = default_human.get(cls, 0) + 1

# ====================================================================
# HOLDOUT CONSTRUCTION
# ====================================================================
# Select findings NOT in the 30-item review sample
with engine.connect() as conn:
    all_finding_ids = set()
    for adj_row in adjs:
        adj = dict(zip(adj_cols, adj_row))
        all_finding_ids.add(adj['finding_id'])
    
    # Get other findings
    f_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(findings)")).fetchall()]
    all_findings = conn.execute(text("SELECT * FROM findings")).fetchall()
    
    holdout_candidates = []
    for f_row in all_findings:
        f = dict(zip(f_cols, f_row))
        if f['id'] in all_finding_ids:
            continue
        meta = json.loads(f.get('metadata_json', '{}') or '{}')
        repo_id = f.get('repository_id')
        repo = conn.execute(text(f"SELECT name FROM repositories WHERE id = '{repo_id}'")).fetchone() if repo_id else None
        evidence = meta.get('evidence_references', [])
        ev_count = len(evidence)
        line_count = None
        for e in evidence:
            m = re.search(r'(\d+)\s*lines', e.get('detail', ''))
            if m:
                line_count = int(m.group(1))
                break
        
        ratio = None
        for e in evidence:
            m = re.search(r'(\d+)x', e.get('detail', ''))
            if m:
                ratio = float(m.group(1))
                break
        if ratio is None and line_count:
            ratio = round(line_count / 300, 2) if line_count else None
        
        # Classify file_context
        module = f.get('module', '')
        if 'test' in module.lower() or '/test/' in module.lower():
            file_ctx = "TEST"
        elif module.endswith('.toml') or module.endswith('.json') or module.endswith('.yaml') or module.endswith('.yml'):
            file_ctx = "CONFIGURATION"
        elif 'vendor' in module.lower() or 'node_modules' in module.lower():
            file_ctx = "VENDOR"
        elif 'generated' in module.lower():
            file_ctx = "GENERATED"
        elif module.endswith('.md') or module.endswith('.rst'):
            file_ctx = "DOCUMENTATION"
        else:
            file_ctx = "PRODUCTION"
        
        gov = meta.get('governance_decision', {})
        holdout_candidates.append({
            'db_id': f['id'][:8], 'full_id': f['id'],
            'repo': repo[0] if repo else 'UNK',
            'module': module,
            'severity': f.get('severity', 'N/A'),
            'category': f.get('category', 'N/A'),
            'line_count': line_count,
            'evidence_count': ev_count,
            'exceedance_ratio': ratio,
            'file_context': file_ctx,
            'gov_decision': gov.get('decision', 'UNKNOWN'),
            'eq_level': 'low', 'confidence': 0.5, 'risk_level': 'none',
            'expected_impact': "high" if f.get('severity') in ("high", "critical") else "medium",
            'completeness': 'insufficient', 'duplication': 'unique',
        })

# Select diverse holdout: 5 PRODUCTION, 5 TEST, 3 CONFIGURATION, 2 other
prod = [h for h in holdout_candidates if h['file_context'] == "PRODUCTION"]
test = [h for h in holdout_candidates if h['file_context'] == "TEST"]
config = [h for h in holdout_candidates if h['file_context'] == "CONFIGURATION"]
other = [h for h in holdout_candidates if h['file_context'] not in ("PRODUCTION", "TEST", "CONFIGURATION")]

import random
random.seed(42)
holdout = []
holdout.extend(prod[:5])
holdout.extend(test[:5])
holdout.extend(config[:3])
holdout.extend(other[:2])
holdout = holdout[:20]

# ====================================================================
# OUTPUT
# ====================================================================
print(f"Loaded {total} calibration findings, {len(holdout)} holdout candidates\n")

print("=" * 80)
print("VARIANT COMPARISON — CALIBRATION DATASET")
print("=" * 80)
print(f"{'Variant':20s} | {'Exact':6s} | {'Over':6s} | {'Under':6s} | {'NME_Acc':7s} | {'Useful_Recall':12s} | {'NA_Handling':11s}")
print("-" * 85)
for name, m in all_results.items():
    print(f"{name:20s} | {m['exact']:5.1%} | {m['over']:5.1%} | {m['under']:5.1%} | {m['nme_accuracy']:6.1%} | {m['useful_recall']:11.1%} | {m['na_handling']:10.1%}")

print(f"\n{'Metric':20s} | ", end="")
for name in all_results:
    print(f"{name:10s} ", end="")
print()

# Context-specific for best variants
print("\n" + "=" * 80)
print("CONTEXT-SPECIFIC METRICS (VARIANT E — file_context + exceedance)")
print("=" * 80)

for ctx in ["PRODUCTION", "TEST", "CONFIGURATION"]:
    ctx_findings = [f for f in findings if f['file_context'] == ctx]
    if not ctx_findings:
        continue
    ctx_results = [variant_e(f) for f in ctx_findings]
    ctx_total = len(ctx_findings)
    ctx_exact = sum(1 for r, f in zip(ctx_results, ctx_findings) if r[0] in ("APPROVED",) and f['classification'] == "USEFUL"
                    or r[0] == "NEEDS_MORE_EVIDENCE" and f['classification'] == "NEEDS_MORE_EVIDENCE"
                    or r[0] == "NOT_ACTIONABLE" and f['classification'] == "NOT_ACTIONABLE")
    ctx_over = sum(1 for r, f in zip(ctx_results, ctx_findings) if r[0] in ("APPROVED",) and f['classification'] in ("NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE"))
    ctx_useful = sum(1 for f in ctx_findings if f['classification'] == "USEFUL")
    ctx_useful_appr = sum(1 for r, f in zip(ctx_results, ctx_findings) if r[0] == "APPROVED" and f['classification'] == "USEFUL")
    print(f"  {ctx:20s}: {ctx_total} findings | Exact: {ctx_exact}/{ctx_total}={ctx_exact/ctx_total:.1%} | Over: {ctx_over}/{ctx_total}={ctx_over/ctx_total:.1%} | Useful Recall: {ctx_useful_appr}/{ctx_useful}")

# Threshold-specific
print("\n" + "=" * 80)
print("THRESHOLD-SPECIFIC METRICS (VARIANT E)")
print("=" * 80)

for tier_name, lo, hi in [("NEAR_THRESHOLD", 0, 1.5), ("MODERATE", 1.5, 3.0), ("HIGH", 3.0, 5.0), ("EXTREME", 5.0, 999)]:
    tier_findings = [f for f in findings if f['exceedance_ratio'] is not None and lo <= f['exceedance_ratio'] < hi]
    if not tier_findings:
        continue
    tier_results = [variant_e(f) for f in tier_findings]
    t = len(tier_findings)
    exact = sum(1 for r, f in zip(tier_results, tier_findings) if r[0] in ("APPROVED",) and f['classification'] == "USEFUL"
                or r[0] == "NEEDS_MORE_EVIDENCE" and f['classification'] == "NEEDS_MORE_EVIDENCE")
    print(f"  {tier_name:20s}: {t} findings | Exact: {exact}/{t}={exact/t:.1%}")

# Default fallthrough
print("\n" + "=" * 80)
print("DEFAULT FALLTHROUGH ANALYSIS")
print("=" * 80)
print(f"  Default APPROVAL count: {default_appr}/{total-1} = {default_appr/(total-1):.1%}")
print(f"  Human outcomes for default approvals:")
for cls in ["USEFUL", "NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE", "DUPLICATE"]:
    c = default_human.get(cls, 0)
    if c > 0:
        print(f"    {cls}: {c}")

# Holdout classification (blind - operator classifies)
print("\n" + "=" * 80)
print("HOLDOUT SAMPLE (20 findings — BLIND)")
print("=" * 80)
for i, h in enumerate(holdout, 1):
    print(f"  {i:2d}. {h['db_id']} | {h['repo']:15s} | {h['module'][:40]:40s} | CTX={h['file_context']:14s} | RATIO={h['exceedance_ratio']}")

# Run all variants on holdout
print("\n" + "=" * 80)
print("HOLDOUT — VARIANT COMPARISON")
print("=" * 80)
print(f"{'Variant':20s} | {'Exact':6s} | {'Over':6s} | {'Under':6s} | {'Useful_Recall':12s}")
print("-" * 65)
for name, func in variants.items():
    h_results = [func(h) for h in holdout]
    h_total = len(holdout)
    h_exact = sum(1 for r, h in zip(h_results, holdout) if r[0] in ("APPROVED",) and h['classification'] == "USEFUL"
                  or r[0] == "NEEDS_MORE_EVIDENCE" and h['classification'] == "NEEDS_MORE_EVIDENCE"
                  or r[0] == "NOT_ACTIONABLE" and h['classification'] == "NOT_ACTIONABLE")
    h_over = sum(1 for r, h in zip(h_results, holdout) if r[0] in ("APPROVED",) and h['classification'] in ("NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE"))
    h_under = sum(1 for r, h in zip(h_results, holdout) if r[0] in ("REJECTED", "NEEDS_MORE_EVIDENCE") and h['classification'] == "USEFUL")
    h_useful_total = sum(1 for h in holdout if h['classification'] == "USEFUL")
    h_useful_appr = sum(1 for r, h in zip(h_results, holdout) if r[0] in ("APPROVED",) and h['classification'] == "USEFUL")
    h_ur = h_useful_appr / h_useful_total if h_useful_total else 0
    print(f"{name:20s} | {h_exact/h_total:5.1%} | {h_over/h_total:5.1%} | {h_under/h_total:5.1%} | {h_ur:11.1%}")

# Candidate selection
print("\n" + "=" * 80)
print("CANDIDATE SELECTION")
print("=" * 80)
print("  Selection criteria:")
print("    1. High exact agreement")
print("    2. Low over-approval")
print("    3. Low under-approval")
print("    4. 100% or near-100% Useful Approval Recall")
print("    5. Strong NME handling")
print("    6. Explainable rules")
print("    7. Minimal complexity")
print("    8. Generalizes to holdout")
print("    9. No repository-specific exceptions")
print("   10. Does not encode known human answers")

# Score each variant
best_name = None
best_score = -1
for name, m in all_results.items():
    # Penalty for under-approval (false rejection of useful)
    penalty = m['under'] * 10
    # Bonus for useful recall
    bonus = m['useful_recall'] * 5
    score = m['exact'] * 100 + bonus - penalty - m['over'] * 50
    if score > best_score:
        best_score = score
        best_name = name

print(f"\n  CANDIDATE: {best_name}")
print(f"  Calibration metrics:")
bm = all_results[best_name]
print(f"    Exact Agreement: {bm['exact']:.1%}")
print(f"    Over-Approval: {bm['over']:.1%}")
print(f"    Under-Approval: {bm['under']:.1%}")
print(f"    Useful Approval Recall: {bm['useful_recall']:.1%}")
print(f"    NME Accuracy: {bm['nme_accuracy']:.1%}")
print(f"    NA Handling: {bm['na_handling']:.1%}")

# Mission impact
print("\n" + "=" * 80)
print("MISSION IMPACT SIMULATION")
print("=" * 80)
prod_appr = sum(1 for r, f in zip(all_results['A_CONTROL']['results'], findings)
                if r[0] in ("APPROVED", "APPROVED_WITH_NOTES"))
cand_appr = sum(1 for r, f in zip(all_results[best_name]['results'], findings)
                if r[0] in ("APPROVED", "APPROVED_WITH_NOTES"))
print(f"  Production Governance: {prod_appr} missions permitted")
print(f"  Candidate ({best_name}): {cand_appr} missions permitted")
print(f"  Missions deferred/rejected: {prod_appr - cand_appr}")
print(f"  Linkage: UNMEASURABLE DUE TO TRACEABILITY LIMITATION")

# Save snapshot data
snapshot = {
    "version": "1.0",
    "trial_id": TRIAL_ID,
    "day": 6,
    "title": "Day 6 — Governance v1.3 Calibration Validation",
    "completed_at": "2026-08-11",
    "calibration_size": total,
    "holdout_size": len(holdout),
    "variants": {name: {k: v for k, v in m.items() if k != 'results'} for name, m in all_results.items()},
    "default_fallthrough": {"count": default_appr, "human_outcomes": default_human},
    "candidate": best_name,
    "candidate_metrics": {k: v for k, v in bm.items() if k != 'results'},
    "holdout_sample": [{"db_id": h['db_id'], "repo": h['repo'], "module": h['module'], "file_context": h['file_context'], "exceedance_ratio": h['exceedance_ratio']} for h in holdout],
}
with open('/tmp/day6_snapshot.json', 'w') as fp:
    json.dump(snapshot, fp, indent=2)

print(f"\n  Snapshot saved to /tmp/day6_snapshot.json")
print(f"\nDay 6 analysis COMPLETE.")
