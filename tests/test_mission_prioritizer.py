"""Regression tests for mission_prioritizer.py.

Covers 25 focused tests as required by Cycle 6.
"""

from __future__ import annotations

import pytest
from hermes_v01.mission_prioritizer import (
    PrioritizationResult,
    PriorityReason,
    compute_priority_score,
    prioritize_missions,
    mission_priority_to_dict,
    prioritization_result_to_dict,
    _priority_band_from_score,
    _determine_selection_status,
    _get_human_classification,
)


def _make_mission(
    mission_id: str = "MISSION-001",
    finding_id: str = "FINDING-001",
    severity: str = "medium",
    human_classification: str = "UNREVIEWED",
    governance_decision: str = "APPROVED",
    file_context: str = "hermes_v01/mission.py",
    evidence_count: int = 1,
) -> dict:
    evidence_refs = [
        {"source": "complexity_signals", "reference_path": file_context, "detail": f"Evidence {i}"}
        for i in range(evidence_count)
    ]
    return {
        "mission_id": mission_id,
        "originating_finding_id": finding_id,
        "finding_severity": severity,
        "human_classification": human_classification,
        "governance_decision": governance_decision,
        "file_context": file_context,
        "evidence_references": evidence_refs,
        "finding": {"human_classification": human_classification},
    }


# Test 1
def test_higher_priority_outranks_lower():
    high = _make_mission(mission_id="HIGH", severity="high", human_classification="USEFUL")
    low = _make_mission(mission_id="LOW", severity="low", human_classification="NOT_ACTIONABLE")
    result = prioritize_missions([high, low], limit=50)
    assert result.selected_count == 1
    assert result.selected[0].mission_id == "HIGH"
    assert result.suppressed_count == 1
    assert result.suppressed[0].mission_id == "LOW"


# Test 2
def test_ranking_is_deterministic():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium") for i in range(20)]
    r1 = prioritize_missions(missions, limit=50)
    r2 = prioritize_missions(missions, limit=50)
    for a, b in zip(r1.selected, r2.selected):
        assert a.mission_id == b.mission_id
        assert a.priority_score == b.priority_score


# Test 3
def test_stable_tie_breaking():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium") for i in range(10)]
    r1 = prioritize_missions(missions, limit=50)
    r2 = prioritize_missions(missions, limit=50)
    for a, b in zip(r1.selected, r2.selected):
        assert a.mission_id == b.mission_id


# Test 4
def test_50_cap_enforced():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium") for i in range(100)]
    result = prioritize_missions(missions, limit=50)
    assert result.selected_count == 50
    assert result.deferred_count == 50


# Test 5
def test_mission_51_deferred_not_lost():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium") for i in range(60)]
    result = prioritize_missions(missions, limit=50)
    deferred_ids = [mp.mission_id for mp in result.deferred]
    assert "M-050" in deferred_ids


# Test 6
def test_deferred_mission_retains_linkage():
    missions = [_make_mission(mission_id=f"M-{i:03d}", finding_id=f"F-{i:03d}") for i in range(60)]
    result = prioritize_missions(missions, limit=50)
    for mp in result.deferred:
        assert mp.mission_id.startswith("M-")


# Test 7
def test_selected_mission_retains_linkage():
    missions = [_make_mission(mission_id=f"M-{i:03d}", finding_id=f"F-{i:03d}") for i in range(30)]
    result = prioritize_missions(missions, limit=50)
    for mp in result.selected:
        assert mp.mission_id.startswith("M-")


# Test 8
def test_100_percent_traceability():
    missions = [_make_mission(mission_id=f"M-{i:03d}", finding_id=f"F-{i:03d}") for i in range(70)]
    result = prioritize_missions(missions, limit=50)
    all_ids = set()
    for mp in result.selected:
        all_ids.add(mp.mission_id)
    for mp in result.deferred:
        all_ids.add(mp.mission_id)
    for mp in result.suppressed:
        all_ids.add(mp.mission_id)
    assert len(all_ids) == result.candidate_count


# Test 9
def test_useful_raises_priority():
    useful = _make_mission(mission_id="USEFUL", human_classification="USEFUL")
    unreviewed = _make_mission(mission_id="UNR", human_classification="UNREVIEWED")
    result = prioritize_missions([useful, unreviewed], limit=50)
    assert result.selected[0].mission_id == "USEFUL"


# Test 10
def test_not_actionable_suppressed():
    na = _make_mission(mission_id="NA", human_classification="NOT_ACTIONABLE")
    unr = _make_mission(mission_id="UNR", human_classification="UNREVIEWED")
    result = prioritize_missions([na, unr], limit=50)
    assert result.suppressed_count == 1
    assert result.suppressed[0].mission_id == "NA"


# Test 11
def test_false_positive_suppressed():
    fp = _make_mission(mission_id="FP", human_classification="FALSE_POSITIVE")
    unr = _make_mission(mission_id="UNR", human_classification="UNREVIEWED")
    result = prioritize_missions([fp, unr], limit=50)
    assert result.suppressed_count == 1
    assert result.suppressed[0].mission_id == "FP"


# Test 12
def test_duplicate_suppressed():
    dup = _make_mission(mission_id="DUP", human_classification="DUPLICATE")
    unr = _make_mission(mission_id="UNR", human_classification="UNREVIEWED")
    result = prioritize_missions([dup, unr], limit=50)
    assert result.suppressed_count == 1
    assert result.suppressed[0].mission_id == "DUP"


# Test 13
def test_nme_lower_priority():
    nme = _make_mission(mission_id="NME", human_classification="NEEDS_MORE_EVIDENCE")
    unr = _make_mission(mission_id="UNR", human_classification="UNREVIEWED")
    result = prioritize_missions([nme, unr], limit=50)
    assert result.selected_count == 2
    nme_mp = next(mp for mp in result.selected if mp.mission_id == "NME")
    unr_mp = next(mp for mp in result.selected if mp.mission_id == "UNR")
    assert nme_mp.priority_score < unr_mp.priority_score


# Test 14
def test_unreviewed_eligible():
    missions = [_make_mission(mission_id=f"M-{i:03d}", human_classification="UNREVIEWED") for i in range(30)]
    result = prioritize_missions(missions, limit=50)
    assert result.selected_count == 30


# Test 15
def test_no_human_review_works():
    missions = [_make_mission(mission_id=f"M-{i:03d}", human_classification="UNKNOWN") for i in range(60)]
    result = prioritize_missions(missions, limit=50)
    assert result.selected_count == 50
    assert result.deferred_count == 10


# Test 16
def test_priority_reasons_persisted():
    mission = _make_mission(severity="high", human_classification="USEFUL", evidence_count=3)
    result = prioritize_missions([mission], limit=50)
    mp = result.selected[0]
    assert len(mp.priority_reasons) > 0
    factors = {r.factor for r in mp.priority_reasons}
    assert "severity" in factors


# Test 17
def test_priority_rank_persisted():
    missions = [_make_mission(mission_id=f"M-{i:03d}") for i in range(10)]
    result = prioritize_missions(missions, limit=50)
    for i, mp in enumerate(result.selected, 1):
        assert mp.priority_rank == i


# Test 18
def test_identical_input_identical_output():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium") for i in range(25)]
    r1 = prioritize_missions(missions, limit=50)
    r2 = prioritize_missions(missions, limit=50)
    assert len(r1.selected) == len(r2.selected)
    for a, b in zip(r1.selected, r2.selected):
        assert a.mission_id == b.mission_id
        assert a.priority_score == b.priority_score


# Test 19
def test_over_50_ranked_before_cap():
    missions = [_make_mission(mission_id=f"M-{i:03d}", severity="medium" if i < 50 else "low") for i in range(100)]
    result = prioritize_missions(missions, limit=50)
    assert result.selected_count == 50
    min_sel = min(mp.priority_score for mp in result.selected)
    max_def = max(mp.priority_score for mp in result.deferred)
    assert min_sel >= max_def


# Test 20
def test_under_50_unaffected():
    missions = [_make_mission(mission_id=f"M-{i:03d}") for i in range(30)]
    result = prioritize_missions(missions, limit=50)
    assert result.selected_count == 30
    assert result.deferred_count == 0


# Test 21
def test_zero_candidates():
    result = prioritize_missions([], limit=50)
    assert result.candidate_count == 0
    assert result.selected_count == 0
    assert result.deferred_count == 0


# Test 22
def test_legacy_mission_handled_safely():
    legacy = {"mission_id": "LEGACY", "finding_severity": "medium"}
    result = prioritize_missions([legacy], limit=50)
    assert result.selected_count == 1
    assert result.selected[0].mission_id == "LEGACY"


# Test 23
def test_api_serialization():
    missions = [_make_mission(mission_id=f"M-{i:03d}") for i in range(5)]
    result = prioritize_missions(missions, limit=50)
    d = prioritization_result_to_dict(result)
    assert "selected" in d
    assert "deferred" in d
    assert "suppressed" in d
    assert d["candidate_count"] == 5
    assert len(d["selected"]) == 5


# Test 24
def test_journal_event_data():
    missions = [_make_mission(mission_id=f"M-{i:03d}") for i in range(10)]
    result = prioritize_missions(missions, limit=50, repository="test-repo")
    d = prioritization_result_to_dict(result)
    assert d["repository"] == "test-repo"
    assert d["cap"] == 50
    assert d["candidate_count"] == 10


# Test 25
def test_no_repository_mutation():
    missions = [_make_mission(mission_id=f"M-{i:03d}") for i in range(10)]
    original_ids = [m["mission_id"] for m in missions]
    result = prioritize_missions(missions, limit=50)
    current_ids = [m["mission_id"] for m in missions]
    assert original_ids == current_ids
