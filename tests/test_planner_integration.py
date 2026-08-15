"""Tests for Mission Recommendation → Planner Integration v1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evosia.mission import Mission, MissionPlanner, MissionTask, RetryPolicy
from evosia.mission_recommendation_models import (
    DraftMission,
    GeneratedTask,
    MissionRecommendations,
    TraceabilityLink,
    _VALID_STATES,
)
from evosia.mission_generator import generate_missions
from evosia.draft_mission_translator import (
    translate_draft_to_mission,
    validate_draft_for_planning,
    is_approved_draft,
)

HERMES_ROOT = Path(__file__).resolve().parent.parent
PLANNER = MissionPlanner()


def _gov_gate_only() -> dict:
    """Gate-mode governance: the machine emits NO approvals (human authority only)."""
    return {
        "repository": {"name": "test", "path": "/tmp/test"},
        "assessment": {
            "recommendation_assessments": [],
            # Gate vocabulary: no machine APPROVED/REJECTED decisions, no
            # machine-authorized missions. Mission eligibility requires a human
            # ACTIONABLE adjudication passed separately via actionable_findings.
            "approval_decisions": [],
            "conflicts": [],
            "duplicates": [],
            "approved_missions": [],
            "summary": {"total_evaluated": 2, "approved": 0, "approved_with_notes": 0,
                        "needs_more_evidence": 0, "deferred": 0, "rejected": 0,
                        "conflicts_found": 0, "duplicates_found": 0, "approval_rate": 0.0},
        },
    }


def _human_actionable_findings() -> list[dict]:
    """Findings carrying explicit human ACTIONABLE adjudications (gate path)."""
    return [
        {"finding_id": "F-001", "recommendation": "Add tests", "priority_score": 5.0,
         "effort": "small", "risk": "low", "mission_type": "testing_improvements",
         "affected_modules": ["src/main.py"], "severity": "medium",
         "human_classification": "ACTIONABLE", "governance_decision": "ACTIONABLE",
         "evidence_references": []},
        {"finding_id": "F-002", "recommendation": "Fix docs", "priority_score": 4.0,
         "effort": "trivial", "risk": "none", "mission_type": "documentation_refresh",
         "affected_modules": [], "severity": "medium",
         "human_classification": "ACTIONABLE", "governance_decision": "ACTIONABLE",
         "evidence_references": []},
    ]


def _gov_with_human_actionable() -> dict:
    """Gate-mode gov where mission eligibility flows from human ACTIONABLE
    adjudications. The CLI's _actionable_from_gov treats approved_missions as
    human-adjudicated ACTIONABLE admissions, so missions are produced via the
    human authority path (machine never APPROVES)."""
    return {
        "repository": {"name": "test", "path": "/tmp/test"},
        "assessment": {
            "recommendation_assessments": [],
            "approval_decisions": [],
            "conflicts": [],
            "duplicates": [],
            "approved_missions": _human_actionable_findings(),
            "summary": {"total_evaluated": 2, "approved": 0, "approved_with_notes": 0,
                        "needs_more_evidence": 0, "deferred": 0, "rejected": 0,
                        "conflicts_found": 0, "duplicates_found": 0, "approval_rate": 0.0},
        },
    }


def _draft_mission(state: str = "DRAFT", **overrides) -> DraftMission:
    trace = TraceabilityLink(
        governance_finding_id="G-1", engineering_finding_id="E-1",
        recommendation_text="Rec", repository_intelligence_source="src",
        evidence_summary="Evidence",
    )
    tasks = (GeneratedTask(task_id="t1", title="T", command=["echo", "hi"]),)
    defaults = dict(
        mission_id="M-001", title="Title", description="Desc", objective="Obj",
        tasks=tasks, state=state, traceability=trace,
        originating_finding_id="F-1", originating_recommendation="Rec",
        governance_approval_reference="GOV-F-1", mission_type="testing_improvements",
    )
    defaults.update(overrides)
    return DraftMission(**defaults)


# ---------------------------------------------------------------------------
# 1. Approve draft
# ---------------------------------------------------------------------------

class TestApprove:
    def test_approve_sets_state(self):
        m = _draft_mission(state="DRAFT")
        approved = m.approve(by="tester")
        assert approved.state == "APPROVED"
        assert approved.approved_by == "tester"

    def test_approve_sets_timestamp(self):
        m = _draft_mission(state="DRAFT")
        approved = m.approve()
        assert approved.approved_at != ""
        assert "T" in approved.approved_at

    def test_approve_preserves_traceability(self):
        m = _draft_mission(state="DRAFT")
        approved = m.approve()
        assert approved.traceability is not None
        assert approved.traceability.governance_finding_id == "G-1"

    def test_approve_preserves_tasks(self):
        m = _draft_mission(state="DRAFT")
        approved = m.approve()
        assert len(approved.tasks) == 1
        assert approved.tasks[0].task_id == "t1"


# ---------------------------------------------------------------------------
# 2. Reject draft
# ---------------------------------------------------------------------------

class TestReject:
    def test_reject_sets_state(self):
        m = _draft_mission(state="DRAFT")
        rejected = m.reject(reason="too expensive")
        assert rejected.state == "REJECTED"
        assert rejected.rejection_reason == "too expensive"

    def test_reject_preserves_traceability(self):
        m = _draft_mission(state="DRAFT")
        rejected = m.reject()
        assert rejected.traceability is not None


# ---------------------------------------------------------------------------
# 3. Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_draft_status(self):
        m = _draft_mission(state="DRAFT")
        assert m.state == "DRAFT"
        assert m.is_draft
        assert not m.is_approved
        assert not m.is_rejected

    def test_approved_status(self):
        m = _draft_mission(state="APPROVED", approved_at="2026-01-01T00:00:00Z", approved_by="h")
        assert m.state == "APPROVED"
        assert m.is_approved
        assert not m.is_draft

    def test_rejected_status(self):
        m = _draft_mission(state="REJECTED", rejection_reason="no")
        assert m.state == "REJECTED"
        assert m.is_rejected


# ---------------------------------------------------------------------------
# 4. Duplicate approval idempotency
# ---------------------------------------------------------------------------

class TestDuplicateApproval:
    def test_cannot_approve_twice(self):
        m = _draft_mission(state="DRAFT").approve()
        with pytest.raises(ValueError, match="Cannot approve"):
            m.approve()

    def test_cannot_reject_after_approve(self):
        m = _draft_mission(state="DRAFT").approve()
        with pytest.raises(ValueError, match="Cannot reject"):
            m.reject()

    def test_cannot_approve_after_reject(self):
        m = _draft_mission(state="DRAFT").reject()
        with pytest.raises(ValueError, match="Cannot approve"):
            m.approve()


# ---------------------------------------------------------------------------
# 5. Rejected mission cannot be approved without reset
# ---------------------------------------------------------------------------

class TestResetPolicy:
    def test_rejected_mission_rejects_approve(self):
        m = _draft_mission(state="DRAFT").reject()
        with pytest.raises(ValueError, match="Cannot approve"):
            m.approve()
        assert m.state == "REJECTED"


# ---------------------------------------------------------------------------
# 6. Draft rejected by planner
# ---------------------------------------------------------------------------

class TestPlannerRejectsDraft:
    def test_draft_cannot_translate(self):
        m = _draft_mission(state="DRAFT")
        with pytest.raises(ValueError, match="not APPROVED"):
            translate_draft_to_mission(m)

    def test_draft_fails_validation(self):
        m = _draft_mission(state="DRAFT")
        errors = validate_draft_for_planning(m)
        assert len(errors) == 1
        assert "not APPROVED" in errors[0]

    def test_draft_fails_plan_build(self):
        m = _draft_mission(state="DRAFT")
        errors = validate_draft_for_planning(m)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 7. Rejected artifact rejected by planner
# ---------------------------------------------------------------------------

class TestPlannerRejectsRejected:
    def test_rejected_cannot_translate(self):
        m = _draft_mission(state="REJECTED")
        with pytest.raises(ValueError, match="not APPROVED"):
            translate_draft_to_mission(m)


# ---------------------------------------------------------------------------
# 8. Approved artifact accepted by planner
# ---------------------------------------------------------------------------

class TestPlannerAcceptsApproved:
    def test_approved_translates(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.mission_id == "M-001"
        assert mission.metadata.get("recommendation_generated") is True

    def test_approved_plan_builds(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        plan = PLANNER.build(mission)
        assert plan.valid
        assert len(plan.errors) == 0

    def test_plan_has_tasks(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        plan = PLANNER.build(mission)
        assert len(plan.tasks) == 1
        assert plan.tasks[0].task_id == "t1"


# ---------------------------------------------------------------------------
# 9. Traceability preserved
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_traceability_in_translated_mission(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert "traceability" in mission.metadata
        trace = mission.metadata["traceability"]
        assert trace["governance_finding_id"] == "G-1"

    def test_traceability_in_plan_metadata(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        plan = PLANNER.build(mission)
        assert plan.mission_id == "M-001"

    def test_governance_reference_preserved(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.metadata["governance_approval_reference"] == "GOV-F-1"

    def test_originating_finding_preserved(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.metadata["originating_finding_id"] == "F-1"


# ---------------------------------------------------------------------------
# 10. Generated tasks map correctly
# ---------------------------------------------------------------------------

class TestTaskMapping:
    def test_task_id_preserved(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.tasks[0].task_id == "t1"

    def test_task_command_preserved(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.tasks[0].command == ["echo", "hi"]

    def test_task_title_preserved(self):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        assert mission.tasks[0].title == "T"


# ---------------------------------------------------------------------------
# 11. Constraints preserved
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_constraints_preserved(self):
        m = _draft_mission(state="DRAFT", constraints=("no auto-execute",))
        approved = m.approve()
        mission = translate_draft_to_mission(approved)
        assert "no auto-execute" in mission.constraints


# ---------------------------------------------------------------------------
# 12. Capabilities preserved
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_capabilities_preserved(self):
        m = _draft_mission(state="DRAFT", required_capabilities=("analyzer",))
        approved = m.approve()
        mission = translate_draft_to_mission(approved)
        assert "analyzer" in mission.required_capabilities


# ---------------------------------------------------------------------------
# 13. Deterministic plan output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_plan(self):
        m = _draft_mission(state="DRAFT").approve()
        mission1 = translate_draft_to_mission(m)
        mission2 = translate_draft_to_mission(m)
        plan1 = PLANNER.build(mission1)
        plan2 = PLANNER.build(mission2)
        assert plan1.plan_hash == plan2.plan_hash

    def test_plan_hash_differs_for_different_tasks(self):
        m1 = _draft_mission(state="DRAFT", mission_id="M-001")
        m2 = _draft_mission(state="DRAFT", mission_id="M-002")
        mission1 = translate_draft_to_mission(m1.approve())
        mission2 = translate_draft_to_mission(m2.approve())
        plan1 = PLANNER.build(mission1)
        plan2 = PLANNER.build(mission2)
        assert plan1.plan_hash == plan2.plan_hash  # Same tasks → same hash


# ---------------------------------------------------------------------------
# 14. Malformed approval metadata
# ---------------------------------------------------------------------------

class TestMalformedMetadata:
    def test_missing_traceability_fails(self):
        m = _draft_mission(state="DRAFT")
        m_no_trace = DraftMission(
            mission_id=m.mission_id, title=m.title, description=m.description,
            objective=m.objective, tasks=m.tasks, state="DRAFT",
            traceability=None,
        )
        approved = m_no_trace.approve()
        errors = validate_draft_for_planning(approved)
        assert any("missing governance traceability" in e for e in errors)

    def test_missing_gov_ref_fails(self):
        m = _draft_mission(state="DRAFT", governance_approval_reference="")
        approved = m.approve()
        errors = validate_draft_for_planning(approved)
        assert any("missing governance approval reference" in e for e in errors)

    def test_no_tasks_fails(self):
        m = _draft_mission(state="DRAFT", tasks=())
        approved = m.approve()
        errors = validate_draft_for_planning(approved)
        assert any("no tasks" in e for e in errors)


# ---------------------------------------------------------------------------
# 15. CLI integration
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args):
        return subprocess.run(
            [sys.executable, "-m", "evosia.mission_recommendation_cli", *args],
            capture_output=True, text=True, timeout=30,
        )

    def test_generate_then_approve(self, tmp_path):
        gov = _gov_with_human_actionable()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"
        r = self._run(["--repo", str(tmp_path), "--input", str(gov_path),
                        "--output-dir", str(out), "generate"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["total_missions"] == 2

        r2 = self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                         "approve", "REC-MISSION-001"])
        assert r2.returncode == 0
        data2 = json.loads(r2.stdout)
        assert data2["status"] == "approved"
        assert data2["state"] == "APPROVED"

    def test_approve_reject_then_status(self, tmp_path):
        gov = _gov_with_human_actionable()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"
        self._run(["--repo", str(tmp_path), "--input", str(gov_path),
                    "--output-dir", str(out), "generate"])

        r = self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                        "reject", "REC-MISSION-002", "--reason", "too risky"])
        assert r.returncode == 0
        assert json.loads(r.stdout)["status"] == "rejected"

        r2 = self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                         "status", "REC-MISSION-002"])
        assert r2.returncode == 0
        assert json.loads(r2.stdout)["state"] == "REJECTED"

    def test_cannot_approve_nonexistent(self, tmp_path):
        gov = _gov_with_human_actionable()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"
        self._run(["--repo", str(tmp_path), "--input", str(gov_path),
                    "--output-dir", str(out), "generate"])
        r = self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                        "approve", "NONEXISTENT"])
        assert r.returncode == 1

    def test_cannot_approve_already_approved(self, tmp_path):
        gov = _gov_with_human_actionable()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"
        self._run(["--repo", str(tmp_path), "--input", str(gov_path),
                    "--output-dir", str(out), "generate"])
        self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                    "approve", "REC-MISSION-001"])
        r = self._run(["--repo", str(tmp_path), "--output-dir", str(out),
                        "approve", "REC-MISSION-001"])
        assert r.returncode == 1

    def test_status_all(self, tmp_path):
        gov = _gov_with_human_actionable()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"
        self._run(["--repo", str(tmp_path), "--input", str(gov_path),
                    "--output-dir", str(out), "generate"])
        r = self._run(["--repo", str(tmp_path), "--output-dir", str(out), "status"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# 16. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_mission_recommendations_still_work(self):
        gov = _gov_gate_only()
        # Machine gate alone yields ZERO missions (no human adjudication).
        recs_gate_only = generate_missions(gov)
        assert recs_gate_only.summary.missions_generated == 0
        # With explicit human ACTIONABLE adjudications, missions are recommended
        # as DRAFT (machine never authorizes execution).
        recs = generate_missions(
            gov,
            actionable_finding_ids={"F-001", "F-002"},
            actionable_findings=_human_actionable_findings(),
        )
        assert recs.summary.missions_generated == 2
        for m in recs.draft_missions:
            assert m.state == "DRAFT"

    def test_draft_mission_as_dict_backward_compat(self):
        m = _draft_mission(state="DRAFT")
        d = m.as_dict()
        assert d["schema_version"] == "1"
        assert d["metadata"]["state"] == "DRAFT"


# ---------------------------------------------------------------------------
# 17. End-to-end validation
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline_with_approval(self, tmp_path):
        gov = _gov_gate_only()
        gov_path = tmp_path / "gov.json"
        gov_path.write_text(json.dumps(gov))
        out = tmp_path / "recs"

        # Machine gate alone produces no missions.
        from evosia.mission_generator import generate_missions
        from evosia.mission_recommendation_renderer import save_artifacts, export_missions
        gate_only = generate_missions(gov)
        assert gate_only.summary.missions_generated == 0

        # Human ACTIONABLE adjudication is the ONLY route to a mission.
        recs = generate_missions(
            gov,
            actionable_finding_ids={"F-001", "F-002"},
            actionable_findings=_human_actionable_findings(),
        )
        save_artifacts(recs, out)
        export_missions(recs, out / "generated_missions")

        # Load missions
        missions = []
        for p in sorted((out / "generated_missions").glob("*.json")):
            data = json.loads(p.read_text())
            from evosia.mission_recommendation_cli import _parse_mission
            missions.append(_parse_mission(data))

        # Approve first
        approved = missions[0].approve()
        assert approved.is_approved

        # Translate to Mission
        mission = translate_draft_to_mission(approved)
        assert mission.metadata["recommendation_generated"] is True
        assert mission.metadata["traceability"]["governance_finding_id"] == "F-001"

        # Build plan
        plan = PLANNER.build(mission)
        assert plan.valid
        assert len(plan.tasks) == 4

        # Second mission stays DRAFT - planner rejects
        draft_mission = missions[1]
        assert draft_mission.is_draft
        errors = validate_draft_for_planning(draft_mission)
        assert len(errors) > 0

        # No automatic enqueue or execution
        assert plan.valid is True  # Valid but not enqueued


# ---------------------------------------------------------------------------
# 18. Plan planner integration with translate
# ---------------------------------------------------------------------------

class TestPlanCLIIntegration:
    def test_approved_mission_validates(self, tmp_path):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        plan = PLANNER.build(mission)
        assert plan.valid

    def test_approved_mission_builds_plan_tasks(self, tmp_path):
        m = _draft_mission(state="DRAFT").approve()
        mission = translate_draft_to_mission(m)
        plan = PLANNER.build(mission)
        assert plan.tasks[0].task_id == "t1"
        assert plan.tasks[0].command == ["echo", "hi"]
