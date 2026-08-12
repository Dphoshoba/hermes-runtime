"""Comprehensive tests for Mission Recommendation Integration v1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_v01.mission_recommendation_models import (
    DraftMission,
    GeneratedTask,
    MissionRecommendationSummary,
    MissionRecommendations,
    TraceabilityLink,
)
from hermes_v01.mission_generator import generate_missions
from hermes_v01.mission_recommendation_renderer import render_json, render_markdown, save_artifacts, export_missions
from hermes_v01.repo_scanner import scan_repository
from hermes_v01.repo_analyzer import analyze_repository
from hermes_v01.engineering_analyzer import analyze_engineering
from hermes_v01.governance_analyzer import govern_engineering


HERMES_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def hermes_gov():
    scan = scan_repository(HERMES_ROOT)
    ri = analyze_repository(scan)
    ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
    ei = analyze_engineering(ri_json)
    ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
    # Legacy mode preserved for reproducibility of the pre-Cycle-8 pathway.
    gov = govern_engineering(ei_json, mode="legacy")
    return json.loads(json.dumps(gov.as_dict(), sort_keys=True))


@pytest.fixture
def tmp_output(tmp_path):
    d = tmp_path / "recs"
    d.mkdir()
    return d


def _gov_with_approved(**overrides) -> dict:
    base = {
        "repository": {"name": "test", "path": "/tmp/test"},
        "assessment": {
            "recommendation_assessments": [],
            "approval_decisions": [{"finding_id": "F-001", "decision": "APPROVED",
                                    "rationale": "Good", "conditions": []}],
            "conflicts": [],
            "duplicates": [],
            "approved_missions": [{"finding_id": "F-001", "recommendation": "Add tests",
                                    "priority_score": 5.0, "effort": "small", "risk": "low",
                                    "mission_type": "testing_improvements", "affected_modules": ["src/main.py"]}],
            "summary": {"total_evaluated": 1, "approved": 1, "approved_with_notes": 0,
                        "needs_more_evidence": 0, "deferred": 0, "rejected": 0,
                        "conflicts_found": 0, "duplicates_found": 0, "approval_rate": 1.0},
        },
    }
    base.update(overrides)
    return base


def _gov_empty() -> dict:
    return {"repository": {"name": "empty"}, "assessment": {
        "recommendation_assessments": [], "approval_decisions": [], "conflicts": [],
        "duplicates": [], "approved_missions": [],
        "summary": {"total_evaluated": 0, "approved": 0, "approved_with_notes": 0,
                    "needs_more_evidence": 0, "deferred": 0, "rejected": 0,
                    "conflicts_found": 0, "duplicates_found": 0, "approval_rate": 0.0}}}


def _actionable_ids(gov: dict) -> set[str]:
    """Human adjudicated ACTIONABLE finding ids (Evidence & Risk Gate contract).

    Under the new architecture a mission requires a human ACTIONABLE
    adjudication. For the preserved legacy pathway these tests validate, the
    legacy approved findings are treated as having been human-adjudicated
    ACTIONABLE so the legacy→mission plumbing stays exercised.
    """
    am = gov.get("assessment", {}).get("approved_missions", [])
    return {m.get("finding_id", "") for m in am if m.get("finding_id")}


# ---------------------------------------------------------------------------
# Data Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_draft_mission_state(self):
        m = DraftMission(mission_id="M-001", title="T", description="D", objective="O",
                         tasks=(GeneratedTask(task_id="t1", title="T", command=["echo", "hi"]),))
        assert m.state == "DRAFT"

    def test_draft_mission_as_dict(self):
        m = DraftMission(mission_id="M-001", title="T", description="D", objective="O",
                         tasks=(GeneratedTask(task_id="t1", title="T", command=["echo", "hi"]),))
        d = m.as_dict()
        assert d["metadata"]["state"] == "DRAFT"
        assert d["mission_id"] == "M-001"

    def test_traceability_link(self):
        t = TraceabilityLink(governance_finding_id="G-1", engineering_finding_id="E-1",
                             recommendation_text="Rec", repository_intelligence_source="src",
                             evidence_summary="Evidence")
        d = t.as_dict()
        assert d["governance_finding_id"] == "G-1"

    def test_generated_task(self):
        t = GeneratedTask(task_id="t1", title="Task", command=["echo", "hi"])
        d = t.as_dict()
        assert d["task_id"] == "t1"
        assert d["command"] == ["echo", "hi"]

    def test_recommendations_default(self):
        r = MissionRecommendations()
        assert r.schema_version == "1"
        assert r.summary.missions_generated == 0


# ---------------------------------------------------------------------------
# Mission Generation Tests
# ---------------------------------------------------------------------------

class TestMissionGeneration:
    def test_generates_from_approved(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.summary.missions_generated == 1

    def test_no_missions_from_empty(self):
        gov = _gov_empty()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.summary.missions_generated == 0

    def test_mission_is_draft(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.draft_missions[0].state == "DRAFT"

    def test_mission_has_tasks(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert len(recs.draft_missions[0].tasks) > 0

    def test_mission_has_traceability(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.draft_missions[0].traceability is not None

    def test_mission_has_governance_reference(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        m = recs.draft_missions[0]
        assert m.governance_approval_reference != ""

    def test_mission_type_counts(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.summary.missions_by_type.get("testing_improvements", 0) == 1

    def test_multiple_approved(self):
        gov = _gov_with_approved(**{
            "assessment": {
                "recommendation_assessments": [],
                "approval_decisions": [
                    {"finding_id": "F-001", "decision": "APPROVED", "rationale": "Good", "conditions": []},
                    {"finding_id": "F-002", "decision": "APPROVED", "rationale": "Good", "conditions": []},
                ],
                "conflicts": [],
                "duplicates": [],
                "approved_missions": [
                    {"finding_id": "F-001", "recommendation": "Add tests", "priority_score": 5.0,
                     "effort": "small", "risk": "low", "mission_type": "testing_improvements",
                     "affected_modules": []},
                    {"finding_id": "F-002", "recommendation": "Fix docs", "priority_score": 4.0,
                     "effort": "trivial", "risk": "none", "mission_type": "documentation_refresh",
                     "affected_modules": []},
                ],
                "summary": {"total_evaluated": 2, "approved": 2, "approved_with_notes": 0,
                            "needs_more_evidence": 0, "deferred": 0, "rejected": 0,
                            "conflicts_found": 0, "duplicates_found": 0, "approval_rate": 1.0},
            },
        })
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        assert recs.summary.missions_generated == 2


# ---------------------------------------------------------------------------
# Schema Compliance Tests
# ---------------------------------------------------------------------------

class TestSchemaCompliance:
    def test_mission_conforms_to_hermes_schema(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        m = recs.draft_missions[0]
        d = m.as_dict()
        # Required fields
        assert "schema_version" in d
        assert "mission_id" in d
        assert "title" in d
        assert "description" in d
        assert "tasks" in d
        assert isinstance(d["tasks"], list)
        assert len(d["tasks"]) > 0
        # Task fields
        t = d["tasks"][0]
        assert "task_id" in t
        assert "title" in t
        assert "command" in t
        assert isinstance(t["command"], list)

    def test_mission_json_valid(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        raw = render_json(recs)
        data = json.loads(raw)
        assert "draft_missions" in data


# ---------------------------------------------------------------------------
# Traceability Tests
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_every_mission_has_traceability(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        for m in recs.draft_missions:
            assert m.traceability is not None
            assert m.traceability.engineering_finding_id != ""
            assert m.traceability.recommendation_text != ""

    def test_traceability_links_to_governance(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        m = recs.draft_missions[0]
        assert m.originating_finding_id == "F-001"


# ---------------------------------------------------------------------------
# Renderer Tests
# ---------------------------------------------------------------------------

class TestRenderer:
    def test_json_valid(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        data = json.loads(render_json(recs))
        assert "draft_missions" in data

    def test_json_roundtrip(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        raw = render_json(recs)
        data = json.loads(raw)
        raw2 = json.dumps(data, indent=2, sort_keys=True)
        assert raw == raw2

    def test_markdown_has_header(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        md = render_markdown(recs)
        assert md.startswith("# Mission Recommendations")

    def test_markdown_has_summary(self):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        md = render_markdown(recs)
        assert "## Summary" in md

    def test_save_artifacts(self, tmp_output):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        jp, mp = save_artifacts(recs, tmp_output)
        assert jp.exists()
        assert mp.exists()

    def test_export_missions(self, tmp_output):
        gov = _gov_with_approved()
        recs = generate_missions(gov, actionable_finding_ids=_actionable_ids(gov))
        exported = export_missions(recs, tmp_output / "missions")
        assert len(exported) == 1
        assert exported[0].exists()
        data = json.loads(exported[0].read_text())
        assert data["metadata"]["state"] == "DRAFT"


# ---------------------------------------------------------------------------
# Determinism Tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_output(self):
        gov = _gov_with_approved()
        r1 = generate_missions(gov)
        r2 = generate_missions(gov)
        assert render_json(r1) == render_json(r2)


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args):
        return subprocess.run([sys.executable, "-m", "hermes_v01.mission_recommendation_cli", *args],
                              capture_output=True, text=True, timeout=30)

    def test_generate(self, tmp_output):
        gov = _gov_with_approved()
        gov_path = tmp_output / "gov.json"
        gov_path.write_text(json.dumps(gov))
        result = self._run(["--input", str(gov_path), "--output-dir", str(tmp_output / "recs"), "generate"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "generated"
        assert data["total_missions"] == 1

    def test_summary(self, tmp_output):
        gov = _gov_with_approved()
        gov_path = tmp_output / "gov.json"
        gov_path.write_text(json.dumps(gov))
        result = self._run(["--input", str(gov_path), "summary"])
        assert result.returncode == 0
        assert "# Mission Recommendations" in result.stdout


# ---------------------------------------------------------------------------
# Malformed Input Tests
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_empty_governance(self):
        recs = generate_missions({})
        assert recs.summary.missions_generated == 0

    def test_no_approved_missions(self):
        recs = generate_missions({"assessment": {"approved_missions": []}})
        assert recs.summary.missions_generated == 0


# ---------------------------------------------------------------------------
# Pipeline Dogfood Tests
# ---------------------------------------------------------------------------

class TestPipelineDogfood:
    def test_full_pipeline(self, hermes_gov):
        recs = generate_missions(hermes_gov, actionable_finding_ids=_actionable_ids(hermes_gov))
        assert recs.summary.missions_generated > 0
        # Every mission traces to governance
        for m in recs.draft_missions:
            assert m.traceability is not None
            assert m.state == "DRAFT"

    def test_no_rejected_becomes_mission(self, hermes_gov):
        recs = generate_missions(hermes_gov, actionable_finding_ids=_actionable_ids(hermes_gov))
        # All missions should have governance approval reference
        for m in recs.draft_missions:
            assert m.governance_approval_reference != ""

    def test_mission_json_valid_for_planner(self, hermes_gov):
        """Verify mission JSON could be consumed by Hermes Planner."""
        recs = generate_missions(hermes_gov, actionable_finding_ids=_actionable_ids(hermes_gov))
        for m in recs.draft_missions:
            d = m.as_dict()
            # Planner expects these fields
            assert "mission_id" in d
            assert "title" in d
            assert "tasks" in d
            assert len(d["tasks"]) > 0
            # Tasks must have command
            for t in d["tasks"]:
                assert "command" in t
                assert isinstance(t["command"], list)
                assert len(t["command"]) > 0
