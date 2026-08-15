"""Engineering Governance — analysis engine.

Consumes Engineering Intelligence JSON and produces governance assessments.
This is a reasoning layer. It never scans, never modifies, never enqueues.
"""

from __future__ import annotations

from typing import Any

from .governance_intel_models import (
    ApprovalDecision,
    ApprovedCandidateMission,
    ArchitectureImpact,
    Conflict,
    DuplicateRecommendation,
    EngineeringGovernance,
    EvidenceQuality,
    GovernanceAssessment,
    RecommendationAssessment,
    ApprovalSummary,
    FindingGate,
    GATE_OBSERVED,
    GATE_CORROBORATED,
    GATE_DUPLICATE,
    GATE_INSUFFICIENT_EVIDENCE,
    GATE_REQUIRES_REVIEW,
)


def _evaluate_evidence(rec: dict[str, Any], findings: dict[str, Any]) -> EvidenceQuality:
    fid = rec.get("finding_id", "")
    f = findings.get(fid, {})
    refs = f.get("evidence_references", [])
    n = len(refs)
    sources = {e.get("source", "") for e in refs}
    diversity = "single_source" if len(sources) <= 1 else ("limited" if len(sources) <= 2 else "diverse")
    paths = {e.get("reference_path", "") for e in refs}
    cp = len([p for p in paths if p])
    consistency = "consistent" if cp >= n * 0.8 else ("partial" if cp >= n * 0.5 else "inconsistent")
    if n >= 3 and diversity == "diverse":
        level = "high"
    elif n >= 2 and consistency != "inconsistent":
        level = "medium"
    else:
        level = "low"
    return EvidenceQuality(level=level, reference_count=n, diversity=diversity, consistency=consistency,
                           reasoning=f"{n} ref(s), {diversity}, {consistency}")


def _assess_impact(rec: dict[str, Any], findings: dict[str, Any]) -> ArchitectureImpact:
    fid = rec.get("finding_id", "")
    f = findings.get(fid, {})
    comps = f.get("affected_components", [])
    n = len(comps)
    cat = f.get("category", "")
    sys_cats = {"Architecture", "Coupling", "Dependencies"}
    pkg_cats = {"Maintainability", "Complexity", "Testing"}
    if n > 5 or cat in sys_cats:
        return ArchitectureImpact(level="system", affected_count=n, reasoning=f"{n} components in {cat}")
    elif n > 2 or cat in pkg_cats:
        return ArchitectureImpact(level="package", affected_count=n, reasoning=f"{n} components in {cat}")
    return ArchitectureImpact(level="local", affected_count=n, reasoning=f"{n} component(s)")


def _detect_duplicates(recs: list[dict[str, Any]]) -> list[DuplicateRecommendation]:
    """Detect duplicate recommendations using normalized text comparison.

    Two recommendations are duplicates if their normalized recommendation text
    is identical (after removing finding-specific suffixes like finding IDs).
    """
    dups: list[DuplicateRecommendation] = []
    seen: dict[str, str] = {}
    num = 0
    for r in recs:
        fid = r.get("finding_id", "")
        text = " ".join(r.get("recommendation", "").lower().split())
        # Strip finding ID suffixes like " (FINDING-123)" for comparison
        import re
        base_text = re.sub(r"\s*\([a-z]+-\d+\)\s*$", "", text).strip()
        if base_text in seen:
            num += 1
            dups.append(DuplicateRecommendation(duplicate_id=f"DUP-{num:03d}", primary=seen[base_text],
                                                 duplicate=fid, similarity="identical",
                                                 reasoning=f"Same recommendation as {seen[base_text]}"))
        else:
            seen[base_text] = fid
    return dups


def _detect_conflicts(recs: list[dict[str, Any]]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    patterns = [("split", "merge", "Cannot split and merge"), ("remove", "add", "Conflicting add/remove"),
                ("deprecate", "extend", "Cannot deprecate and extend"), ("isolate", "integrate", "Conflicting goals")]
    num = 0
    for i, a in enumerate(recs):
        ta = a.get("recommendation", "").lower()
        ca = a.get("category", "")
        for b in recs[i + 1:]:
            tb = b.get("recommendation", "").lower()
            cb = b.get("category", "")
            for pa, pb, desc in patterns:
                if ((pa in ta and pb in tb) or (pb in ta and pa in tb)) and ca == cb:
                    num += 1
                    conflicts.append(Conflict(conflict_id=f"CONFLICT-{num:03d}",
                                              recommendation_a=a.get("finding_id", ""),
                                              recommendation_b=b.get("finding_id", ""),
                                              description=desc, severity="medium"))
    return conflicts


def _assess_one(rec: dict[str, Any], findings: dict[str, Any],
                dup_ids: set[str], pri_ids: set[str]) -> RecommendationAssessment:
    fid = rec.get("finding_id", "")
    f = findings.get(fid, {})
    eq = _evaluate_evidence(rec, findings)
    ai = _assess_impact(rec, findings)
    hr = bool(rec.get("recommendation"))
    hra = bool(rec.get("rationale"))
    hb = bool(rec.get("expected_benefit"))
    comp = "complete" if (hr and hra and hb) else ("partial" if (hr or hra) else "insufficient")
    sev = f.get("severity", "low")
    ac = "consistent" if sev in ("low", "medium") else ("inconsistent" if sev == "critical" else "neutral")
    dup = "primary" if fid in pri_ids else ("duplicate" if fid in dup_ids else "unique")
    return RecommendationAssessment(
        finding_id=fid, evidence_quality=eq, completeness=comp,
        architectural_consistency=ac, duplication=dup, scope=ai.level,
        expected_impact="high" if sev in ("high", "critical") else ("medium" if sev == "medium" else "low"),
        risk_level=rec.get("estimated_risk", "none"), confidence=f.get("confidence", 0.5), notes="")


def _decide(a: RecommendationAssessment) -> ApprovalDecision:
    fid = a.finding_id
    if a.duplication == "duplicate":
        return ApprovalDecision(fid, "REJECTED", "Duplicate; merged", ())
    if a.evidence_quality.level == "low" and a.confidence < 0.4:
        return ApprovalDecision(fid, "NEEDS_MORE_EVIDENCE",
                                f"Low evidence (confidence={a.confidence:.0%})", ("Gather more evidence",))
    if a.risk_level in ("medium", "high") and a.expected_impact == "low":
        return ApprovalDecision(fid, "DEFERRED", f"High risk, low impact", ("Re-evaluate later",))
    if a.completeness == "partial":
        return ApprovalDecision(fid, "APPROVED_WITH_NOTES", "Partially complete",
                                ("Complete details before execution",))
    return ApprovalDecision(fid, "APPROVED", "Sufficiently evidenced and complete", ())


# ---------------------------------------------------------------------------
# Evidence & Risk Gate (Post Cycle 8) — machine authority only
# ---------------------------------------------------------------------------

def _gate_state_from_assessment(a: RecommendationAssessment) -> tuple[str, str, str]:
    """Return (observation_state, gate_state, evidence_sufficiency).

    Never returns ACTIONABLE / NOT_ACTIONABLE. The default is REQUIRES_REVIEW
    (human-authority-default): EVOSIA routes to human review; it does not decide
    actionability.
    """
    observation = GATE_CORROBORATED if a.evidence_quality.diversity != "single_source" \
        else GATE_OBSERVED
    if a.duplication == "duplicate":
        return observation, GATE_DUPLICATE, "INSUFFICIENT"
    if a.evidence_quality.level == "low" or a.confidence < 0.4:
        return observation, GATE_INSUFFICIENT_EVIDENCE, "INSUFFICIENT"
    # Default: route to human review. EVOSIA does not classify actionability.
    return observation, GATE_REQUIRES_REVIEW, "SUFFICIENT"


def _risk_band(risk_level: str, severity: str) -> str:
    if risk_level in ("high",) or severity in ("critical", "high"):
        return "HIGH"
    if risk_level in ("medium",) or severity in ("medium",):
        return "MODERATE"
    return "LOW"


def _gate_review_rank(a: RecommendationAssessment, risk_band: str,
                      evidence_sufficiency: str) -> float:
    risk_w = {"HIGH": 1.0, "MODERATE": 0.6, "LOW": 0.3}[risk_band]
    ev_w = 1.0 if evidence_sufficiency == "SUFFICIENT" else 0.4
    conf_w = 0.5 + a.confidence
    return round(risk_w * ev_w * conf_w, 4)


def _gate(a: RecommendationAssessment, legacy_decision: str | None = None) -> FindingGate:
    observation, gate_state, evidence_sufficiency = _gate_state_from_assessment(a)
    risk_band = _risk_band(a.risk_level, a.scope or "local")
    rank = _gate_review_rank(a, risk_band, evidence_sufficiency)
    note = (
        "Machine gate routes to human review; actionability requires human "
        "adjudication. Static evidence cannot determine USEFUL/NOT_ACTIONABLE."
    )
    if legacy_decision in ("APPROVED", "APPROVED_WITH_NOTES"):
        note = (f"Legacy Governance decision '{legacy_decision}' reinterpreted as "
                f"advisory (LEGACY_APPROVED); re-routed to human review.")
    gate = FindingGate(
        finding_id=a.finding_id,
        observation_state=observation,
        gate_state=gate_state,
        risk_band=risk_band,
        evidence_sufficiency=evidence_sufficiency,
        review_rank=rank,
        uncertainty_note=note,
        evidence_references=tuple(e.as_dict() for e in (a.evidence_quality,)),
        legacy_decision=legacy_decision,
    )
    return gate


def _gen_missions(decisions: list[ApprovalDecision], recs: dict[str, dict[str, Any]],
                  amap: dict[str, RecommendationAssessment]) -> list[ApprovedCandidateMission]:
    missions: list[ApprovedCandidateMission] = []
    type_map = {"Architecture": "architecture_cleanup", "Coupling": "architecture_cleanup",
                "Complexity": "repository_maintenance", "Documentation": "documentation_refresh",
                "Testing": "testing_improvements", "Packaging": "packaging_improvements",
                "Configuration": "configuration_cleanup", "Dependencies": "dependency_review",
                "Security Signals": "dependency_review", "CLI": "documentation_refresh",
                "Public API": "documentation_refresh", "Performance": "repository_maintenance",
                "Maintainability": "repository_maintenance", "Observability": "repository_maintenance",
                "Technical Debt": "repository_maintenance"}
    for d in decisions:
        if d.decision not in ("APPROVED", "APPROVED_WITH_NOTES"):
            continue
        rec = recs.get(d.finding_id, {})
        a = amap.get(d.finding_id)
        if not a:
            continue
        cat = rec.get("category", "Technical Debt")
        affected = tuple(c.get("component_path", "") for c in
                         rec.get("finding", {}).get("affected_components", [])
                         if isinstance(c, dict))
        missions.append(ApprovedCandidateMission(
            finding_id=d.finding_id, recommendation=rec.get("recommendation", ""),
            priority_score=rec.get("priority", {}).get("score", 5.0) if isinstance(rec.get("priority"), dict) else 5.0,
            effort=rec.get("estimated_effort", "small"), risk=a.risk_level,
            mission_type=type_map.get(cat, "repository_maintenance"), affected_modules=affected))
    return missions


def govern_engineering(ei: dict[str, Any], mode: str = "gate") -> EngineeringGovernance:
    """Main entry point. Consume EI dict, produce governance model.

    mode="gate"  (default, Controlled Beta): Evidence & Risk Gate. Machine
        emits FindingGate routings (OBSERVED/CORROBORATED/REQUIRES_REVIEW/...),
        never ACTIONABLE/NOT_ACTIONABLE. approved_missions is empty — no
        automated authorization for missions.
    mode="legacy": reproduces pre-Cycle-8 automated-approval semantics for
        frozen-history replay / reproducibility only. NOT the default
        authorization path.
    """
    repository = ei.get("repository", {})
    recs = ei.get("recommendations", [])
    findings_list = ei.get("findings", [])
    findings_map = {f.get("finding_id", ""): f for f in findings_list}

    dups = _detect_duplicates(recs)
    dup_ids = {d.duplicate for d in dups}
    pri_ids = {d.primary for d in dups}
    conflicts = _detect_conflicts(recs)

    assessments = [_assess_one(r, findings_map, dup_ids, pri_ids) for r in recs]
    amap = {a.finding_id: a for a in assessments}

    if mode == "legacy":
        decisions = tuple(_decide(a) for a in assessments)
        missions = _gen_missions(list(decisions), {r.get("finding_id", ""): r for r in recs}, amap)
        gates: tuple[FindingGate, ...] = ()
        approved = sum(1 for d in decisions if d.decision == "APPROVED")
        awn = sum(1 for d in decisions if d.decision == "APPROVED_WITH_NOTES")
        nme = sum(1 for d in decisions if d.decision == "NEEDS_MORE_EVIDENCE")
        deferred = sum(1 for d in decisions if d.decision == "DEFERRED")
        rejected = sum(1 for d in decisions if d.decision == "REJECTED")
    else:  # gate mode (default)
        decisions = tuple()  # no automated approval decisions emitted
        missions = ()  # no machine-authorized candidate missions
        gates = tuple(_gate(a) for a in assessments)
        # summary counts reflect gate vocabulary
        approved = awn = nme = deferred = rejected = 0

    total = len(assessments)
    rate = (approved + awn) / total if total > 0 else 0.0

    summary = ApprovalSummary(total_evaluated=total, approved=approved, approved_with_notes=awn,
                              needs_more_evidence=nme, deferred=deferred, rejected=rejected,
                              conflicts_found=len(conflicts), duplicates_found=len(dups), approval_rate=rate)

    assessment = GovernanceAssessment(
        recommendation_assessments=tuple(assessments), approval_decisions=decisions,
        conflicts=tuple(conflicts), duplicates=tuple(dups), approved_missions=tuple(missions),
        gate_routings=gates, summary=summary)

    return EngineeringGovernance(repository=repository, assessment=assessment)
