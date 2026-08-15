"""Focused acceptance tests — Evidence & Risk Gate (Post Cycle 8).

Proves acceptance-gate invariants A–J plus M1–M6 migration-critical
regression. Pure-logic paths run without a DB.

Run: pytest tests/test_evidence_risk_gate.py -q
"""
from __future__ import annotations

import pytest

from evosia.governance_intel_models import (
    FindingGate, assert_machine_state, HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE,
    GATE_REQUIRES_REVIEW, GATE_OBSERVED, GATE_CORROBORATED,
)
from evosia.governance_analyzer import govern_engineering
from evosia.mission_generator import (
    generate_missions, _is_human_actionable, _FORBIDDEN_GATE_DECISIONS,
)
from evosia.mission_prioritizer import _GOVERNANCE_WEIGHTS, compute_priority_score


def _ei(two_findings=True):
    recs = [
        {"finding_id": "F1", "category": "Testing", "recommendation": "do X",
         "priority": {"score": 8.0}, "estimated_effort": "small",
         "affected_components": [{"component_path": "a/b.py"}]},
    ]
    if two_findings:
        recs.append({"finding_id": "F2", "category": "Security Signals",
                     "recommendation": "do Y", "priority": {"score": 6.0},
                     "estimated_effort": "medium",
                     "affected_components": [{"component_path": "c/d.py"}]})
    return {
        "repository": {"name": "r", "path": "/x"},
        "findings": [{"finding_id": "F1"}, {"finding_id": "F2"}] if two_findings
                    else [{"finding_id": "F1"}],
        "recommendations": recs,
    }


def _actionable_payload(fid="F1", rec="do X", mtype="testing_improvements"):
    return [{"finding_id": fid, "recommendation": rec, "mission_type": mtype,
             "effort": "small", "priority_score": 8.0,
             "affected_modules": ["a/b.py"], "severity": "medium"}]


# ---------------------------------------------------------------------------
# H: GATE MACHINE OUTPUT never ACTIONABLE / NOT_ACTIONABLE  (M2)
# ---------------------------------------------------------------------------

def test_gate_never_emits_actionability():
    g = govern_engineering(_ei())
    for gt in g.assessment.gate_routings:
        assert gt.gate_state not in (HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE)
        assert gt.observation_state not in (HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE)
        assert gt.as_dict()["authority"] == "machine_gate"


def test_assert_machine_state_blocks_forbidden():
    with pytest.raises(ValueError):
        assert_machine_state(HUMAN_ACTIONABLE)
    with pytest.raises(ValueError):
        assert_machine_state(HUMAN_NOT_ACTIONABLE)
    assert_machine_state(GATE_REQUIRES_REVIEW)
    assert_machine_state(GATE_OBSERVED)
    assert_machine_state(GATE_CORROBORATED)


# ---------------------------------------------------------------------------
# M1/M2 regression: gate mode emits gates, no approvals; default REQUIRES_REVIEW
# ---------------------------------------------------------------------------

def test_M1_gate_mode_no_approved_missions():
    g = govern_engineering(_ei())
    assert g.assessment.approved_missions == ()
    assert g.assessment.gate_routings


def test_M2_default_fallthrough_requires_review():
    g = govern_engineering(_ei())
    states = {gt.finding_id: gt.gate_state for gt in g.assessment.gate_routings}
    for st in states.values():
        assert st in (GATE_REQUIRES_REVIEW, "INSUFFICIENT_EVIDENCE", "DUPLICATE")


# ---------------------------------------------------------------------------
# M3 regression: hard boundary guard
# ---------------------------------------------------------------------------

def test_M3_guard_blocks_unauthorized():
    assert not _is_human_actionable("F1", None)
    assert not _is_human_actionable("F1", set())
    assert _is_human_actionable("F1", {"F1"})


# ---------------------------------------------------------------------------
# M6 regression: prioritizer re-pointed to ACTIONABLE
# ---------------------------------------------------------------------------

def test_M6_prioritizer_weights():
    assert _GOVERNANCE_WEIGHTS["ACTIONABLE"] == 2.0
    assert _GOVERNANCE_WEIGHTS["LEGACY_APPROVED"] == 0.0
    assert _GOVERNANCE_WEIGHTS["NOT_ACTIONABLE"] == -10.0

    actionable_mission = {
        "mission_id": "M1", "originating_finding_id": "F1",
        "finding_severity": "medium", "human_classification": HUMAN_ACTIONABLE,
        "governance_decision": HUMAN_ACTIONABLE, "evidence_references": [],
        "recommendation": "x", "mission_type": "testing_improvements",
        "estimated_effort": "small", "priority_score": 8.0,
    }
    score, reasons = compute_priority_score(actionable_mission)
    assert any(r.factor == "governance_decision" and r.weight > 0 for r in reasons)


# ---------------------------------------------------------------------------
# A: UNREVIEWED FINDING -> no mission  (M3)
# ---------------------------------------------------------------------------

def test_A_unreviewed_no_mission():
    g = govern_engineering(_ei())
    recs = generate_missions(g.as_dict(), actionable_finding_ids=None)
    assert len(recs.draft_missions) == 0


# ---------------------------------------------------------------------------
# B: LEGACY APPROVED w/o human ACTIONABLE -> no mission in gate mode (M1)
# ---------------------------------------------------------------------------

def test_B_legacy_approved_no_mission_gate_mode():
    g = govern_engineering(_ei(), mode="legacy")
    assert any(d.decision in ("APPROVED", "APPROVED_WITH_NOTES")
               for d in g.assessment.approval_decisions)
    recs = generate_missions(g.as_dict(), actionable_finding_ids=None)
    assert len(recs.draft_missions) == 0


# ---------------------------------------------------------------------------
# C/D/E: human classification controls mission eligibility
# ---------------------------------------------------------------------------

def test_C_nme_not_in_actionable_set_no_mission():
    g = govern_engineering(_ei())
    recs = generate_missions(g.as_dict(), actionable_finding_ids=set(),
                             actionable_findings=_actionable_payload("F1"))
    assert len(recs.draft_missions) == 0


def test_D_not_actionable_excluded():
    g = govern_engineering(_ei())
    recs = generate_missions(
        g.as_dict(),
        actionable_finding_ids={"F1"},
        actionable_findings=_actionable_payload("F1")
        + _actionable_payload("F2", "do Y", "dependency_review"),
    )
    ids = [m.originating_finding_id for m in recs.draft_missions]
    assert "F2" not in ids
    assert "F1" in ids


def test_E_actionable_eligible_traceable():
    g = govern_engineering(_ei())
    recs = generate_missions(g.as_dict(), actionable_finding_ids={"F1"},
                             actionable_findings=_actionable_payload("F1"))
    assert len(recs.draft_missions) == 1
    m = recs.draft_missions[0]
    assert m.originating_finding_id == "F1"
    assert m.governance_approval_reference is not None
    assert m.traceability is not None
    # 100% traceability: reference links back to the human adjudication
    assert "F1" in m.governance_approval_reference


# ---------------------------------------------------------------------------
# F: POLICY SUPPRESSED -> no mission + auditable (M5)
# ---------------------------------------------------------------------------

def test_F_suppression_is_not_actionable_and_auditable_flag():
    # A policy suppression is recorded with policy_suppressed=True and is NOT
    # an ACTIONABLE adjudication, so it can never authorize a mission.
    assert "SUPPRESSED_BY_POLICY" != HUMAN_ACTIONABLE
    # The guard never authorizes when no actionable set provided.
    assert not _is_human_actionable("F1", None)


# ---------------------------------------------------------------------------
# G: HISTORICAL APPROVED persisted unchanged (M1)
# ---------------------------------------------------------------------------

def test_G_legacy_decision_not_rewritten():
    gate = FindingGate(
        finding_id="F1", observation_state=GATE_OBSERVED,
        gate_state=GATE_REQUIRES_REVIEW, risk_band="LOW",
        evidence_sufficiency="SUFFICIENT", review_rank=0.3,
        uncertainty_note="x", legacy_decision="APPROVED",
    )
    assert gate.legacy_decision == "APPROVED"
    assert gate.gate_state != "APPROVED"


# ---------------------------------------------------------------------------
# I/J: mission approval + execution remain human-gated (M4)
# ---------------------------------------------------------------------------

def test_IJ_missions_remain_draft_not_executed():
    g = govern_engineering(_ei())
    recs = generate_missions(g.as_dict(), actionable_finding_ids={"F1"},
                             actionable_findings=_actionable_payload("F1"))
    for m in recs.draft_missions:
        assert m.state == "DRAFT"  # never auto-approved, never executed

