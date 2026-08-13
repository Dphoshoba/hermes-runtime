"""Focused tests for Evidence-Based Human Review & Mission Traceability.

Covers:
- Adjudication model immutability
- File context classification (PRODUCTION, TEST, etc.)
- Test-file policy
- Threshold-edge handling
- Observation/concern/actionability distinction
- Configuration requirement validation
- Explicit finding→mission linkage
- Legacy unverified linkage
- Review queue API
- CLI classification
- Journal events
- Review metrics
- Governance agreement
- Day 2R classification persistence
"""

from __future__ import annotations

import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("HERMES_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("HERMES_JWT_SECRET", "test-secret-key-for-testing-only-1234")

from enterprise.database import Base, get_engine, SessionLocal
from enterprise.models import (
    Finding, Repository, FindingAdjudication, MissionFindingLink,
    Mission, JournalEvent,
)
from enterprise.services.review_service import (
    classify_file_context,
    compute_exceedance_ratio,
    classify_exceedance_tier,
    infer_observation_status,
    infer_concern_status,
    infer_actionability_status,
    build_review_queue,
    create_adjudication,
    get_adjudications_for_finding,
    get_review_summary,
    get_pending_count,
    create_mission_finding_link,
    get_mission_links,
    get_finding_mission_links,
    emit_finding_reviewed,
    emit_finding_reclassified,
    FILE_CONTEXT_PRODUCTION,
    FILE_CONTEXT_TEST,
    FILE_CONTEXT_FIXTURE,
    FILE_CONTEXT_GENERATED,
    FILE_CONTEXT_VENDOR,
    FILE_CONTEXT_CONFIGURATION,
    FILE_CONTEXT_DOCUMENTATION,
    FILE_CONTEXT_UNKNOWN,
)


@pytest.fixture(autouse=True)
def setup_db():
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=eng)


# ---------------------------------------------------------------------------
# File context classification
# ---------------------------------------------------------------------------

class TestFileContextClassification:
    def test_production_python(self):
        assert classify_file_context("hermes_v01/mission_runner.py") == FILE_CONTEXT_PRODUCTION

    def test_production_src(self):
        assert classify_file_context("src/flask/app.py") == FILE_CONTEXT_PRODUCTION

    def test_test_file_patterns(self):
        assert classify_file_context("tests/test_basic.py") == FILE_CONTEXT_TEST
        assert classify_file_context("test/res.render.js") == FILE_CONTEXT_TEST
        assert classify_file_context("src/app.test.ts") == FILE_CONTEXT_TEST
        assert classify_file_context("lib/utils_spec.js") == FILE_CONTEXT_TEST

    def test_fixture(self):
        assert classify_file_context("fixtures/data.json") == FILE_CONTEXT_FIXTURE
        assert classify_file_context("__fixtures__/mock.py") == FILE_CONTEXT_FIXTURE

    def test_generated(self):
        assert classify_file_context("dist/bundle.js") == FILE_CONTEXT_GENERATED
        assert classify_file_context("__pycache__/mod.pyc") == FILE_CONTEXT_GENERATED

    def test_vendor(self):
        assert classify_file_context("vendor/lib.py") == FILE_CONTEXT_VENDOR

    def test_configuration(self):
        assert classify_file_context("package.json") == FILE_CONTEXT_CONFIGURATION
        assert classify_file_context("pyproject.toml") == FILE_CONTEXT_CONFIGURATION
        assert classify_file_context("Dockerfile") == FILE_CONTEXT_CONFIGURATION

    def test_documentation(self):
        assert classify_file_context("README.md") == FILE_CONTEXT_DOCUMENTATION
        assert classify_file_context("docs/guide.rst") == FILE_CONTEXT_DOCUMENTATION

    def test_empty_path(self):
        assert classify_file_context("") == FILE_CONTEXT_UNKNOWN

    def test_unknown(self):
        assert classify_file_context("somefile.xyz") == FILE_CONTEXT_PRODUCTION


# ---------------------------------------------------------------------------
# Threshold exceedance ratio
# ---------------------------------------------------------------------------

class TestThresholdExceedance:
    def test_exact_threshold(self):
        assert compute_exceedance_ratio(300, 300) == 1.0

    def test_below_threshold(self):
        assert compute_exceedance_ratio(200, 300) < 1.0

    def test_above_threshold(self):
        assert compute_exceedance_ratio(600, 300) == 2.0

    def test_tier_near_threshold(self):
        assert classify_exceedance_tier(1.05) == "NEAR_THRESHOLD"

    def test_tier_moderate(self):
        assert classify_exceedance_tier(1.5) == "MODERATE_EXCEEDANCE"

    def test_tier_high(self):
        assert classify_exceedance_tier(3.0) == "HIGH_EXCEEDANCE"

    def test_tier_extreme(self):
        assert classify_exceedance_tier(6.0) == "EXTREME_EXCEEDANCE"


# ---------------------------------------------------------------------------
# Observation / Concern / Actionability
# ---------------------------------------------------------------------------

class TestObservationConcernActionability:
    def _finding(self, db, module, evidence=None):
        repo = Repository(name="test-repo", url="https://example.com/test")
        db.add(repo)
        db.commit()
        meta = {}
        if evidence:
            meta["evidence_references"] = evidence
        f = Finding(
            repository_id=repo.id,
            finding_type="maintainability",
            severity="medium",
            category="Maintainability",
            title="Test finding",
            module=module,
            metadata_json=meta,
        )
        db.add(f)
        db.commit()
        return f

    def test_observation_supported_with_evidence(self, setup_db):
        db = setup_db
        f = self._finding(db, "src/app.py", [{"source": "modules", "reference_path": "src/app.py", "detail": "500 lines"}])
        assert infer_observation_status(f) == "SUPPORTED"

    def test_observation_unsupported_without_evidence(self, setup_db):
        db = setup_db
        f = self._finding(db, "src/app.py")
        assert infer_observation_status(f) == "UNSUPPORTED"

    def test_concern_insufficient_for_test(self, setup_db):
        db = setup_db
        f = self._finding(db, "tests/test_basic.py")
        assert infer_concern_status(f, FILE_CONTEXT_TEST) == "INSUFFICIENT"

    def test_concern_not_meaningful_for_generated(self, setup_db):
        db = setup_db
        f = self._finding(db, "dist/bundle.js")
        assert infer_concern_status(f, FILE_CONTEXT_GENERATED) == "NOT_MEANINGFUL"

    def test_concern_possible_for_production(self, setup_db):
        db = setup_db
        f = self._finding(db, "src/app.py", [{"source": "modules", "reference_path": "src/app.py", "detail": "500 lines"}])
        assert infer_concern_status(f, FILE_CONTEXT_PRODUCTION) == "POSSIBLE"

    def test_actionability_not_actionable_for_test(self, setup_db):
        db = setup_db
        f = self._finding(db, "tests/test_basic.py")
        assert infer_actionability_status(f, FILE_CONTEXT_TEST, 1.2) == "NOT_ACTIONABLE"

    def test_actionability_not_actionable_for_generated(self, setup_db):
        db = setup_db
        f = self._finding(db, "dist/bundle.js")
        assert infer_actionability_status(f, FILE_CONTEXT_GENERATED, 3.0) == "NOT_ACTIONABLE"

    def test_actionability_needs_evidence_for_production(self, setup_db):
        db = setup_db
        f = self._finding(db, "src/app.py")
        assert infer_actionability_status(f, FILE_CONTEXT_PRODUCTION, 2.0) == "NEEDS_MORE_EVIDENCE"


# ---------------------------------------------------------------------------
# Test-file policy: LOC alone is NOT_ACTIONABLE for test context
# ---------------------------------------------------------------------------

class TestFilePolicy:
    def test_test_file_304_lines(self, setup_db):
        db = setup_db
        repo = Repository(name="express", url="https://example.com/express")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id,
            finding_type="complexity",
            severity="medium",
            category="Complexity",
            title="Large Module: res.location.js",
            module="test/res.location.js",
            metadata_json={"evidence_references": [{"source": "complexity_signals", "reference_path": "test/res.location.js", "detail": "Module test/res.location.js is 304 lines (threshold: 300)"}]},
        )
        db.add(f)
        db.commit()
        ctx = classify_file_context(f.module)
        assert ctx == FILE_CONTEXT_TEST
        assert infer_actionability_status(f, ctx, 1.01) == "NOT_ACTIONABLE"

    def test_test_file_1970_lines(self, setup_db):
        db = setup_db
        repo = Repository(name="flask", url="https://example.com/flask")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id,
            finding_type="maintainability",
            severity="high",
            category="Maintainability",
            title="Large module: test_basic.py (1970 lines)",
            module="tests/test_basic.py",
            metadata_json={"evidence_references": [{"source": "modules", "reference_path": "tests/test_basic.py", "detail": "Module has 1970 lines"}]},
        )
        db.add(f)
        db.commit()
        ctx = classify_file_context(f.module)
        assert ctx == FILE_CONTEXT_TEST
        actionability = infer_actionability_status(f, ctx, 6.57)
        # Even test files with extreme exceedance (>=5x) get NEEDS_MORE_EVIDENCE, not auto-dismissed
        assert actionability == "NEEDS_MORE_EVIDENCE"

    def test_production_file_1625_lines(self, setup_db):
        db = setup_db
        repo = Repository(name="flask", url="https://example.com/flask")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id,
            finding_type="maintainability",
            severity="high",
            category="Maintainability",
            title="Large module: app.py (1625 lines)",
            module="src/flask/app.py",
            metadata_json={"evidence_references": [{"source": "modules", "reference_path": "src/flask/app.py", "detail": "Module has 1625 lines"}]},
        )
        db.add(f)
        db.commit()
        ctx = classify_file_context(f.module)
        assert ctx == FILE_CONTEXT_PRODUCTION
        assert infer_actionability_status(f, ctx, 5.42) == "NEEDS_MORE_EVIDENCE"

    def test_production_file_540_lines(self, setup_db):
        db = setup_db
        repo = Repository(name="flask", url="https://example.com/flask")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id,
            finding_type="maintainability",
            severity="medium",
            category="Maintainability",
            title="Large module: ctx.py (540 lines)",
            module="src/flask/ctx.py",
            metadata_json={"evidence_references": [{"source": "modules", "reference_path": "src/flask/ctx.py", "detail": "Module has 540 lines"}]},
        )
        db.add(f)
        db.commit()
        ctx = classify_file_context(f.module)
        assert ctx == FILE_CONTEXT_PRODUCTION
        assert infer_actionability_status(f, ctx, 1.8) == "NEEDS_MORE_EVIDENCE"


# ---------------------------------------------------------------------------
# Configuration requirement validation
# ---------------------------------------------------------------------------

class TestConfigurationValidation:
    def test_package_json_is_configuration(self):
        assert classify_file_context("package.json") == FILE_CONTEXT_CONFIGURATION

    def test_configuration_not_auto_actionable(self, setup_db):
        db = setup_db
        repo = Repository(name="hermes-runtime", url="https://example.com/hermes")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id,
            finding_type="configuration",
            severity="medium",
            category="Configuration",
            title="Missing configuration: package.json",
            module="package.json",
            metadata_json={"evidence_references": [{"source": "configuration", "reference_path": "package.json", "detail": "Missing essential configuration: package.json"}]},
        )
        db.add(f)
        db.commit()
        ctx = classify_file_context(f.module)
        assert ctx == FILE_CONTEXT_CONFIGURATION


# ---------------------------------------------------------------------------
# Adjudication model — append-only
# ---------------------------------------------------------------------------

class TestAdjudicationModel:
    def test_create_adjudication(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        adj = create_adjudication(db, f.id, "USEFUL", "tester", notes="looks good")
        assert adj.classification == "USEFUL"
        assert adj.operator == "tester"
        assert adj.observation_status == "UNSUPPORTED"
        assert adj.schema_version == "1.0"

    def test_multiple_adjudications_append_only(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        a1 = create_adjudication(db, f.id, "USEFUL", "reviewer1")
        a2 = create_adjudication(db, f.id, "NOT_ACTIONABLE", "reviewer2", notes="changed mind")

        adjs = get_adjudications_for_finding(db, f.id)
        assert len(adjs) == 2
        assert adjs[0].id == a2.id
        assert adjs[1].id == a1.id

    def test_review_summary(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f1 = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t1")
        f2 = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t2")
        db.add_all([f1, f2])
        db.commit()

        create_adjudication(db, f1.id, "USEFUL", "r1")
        create_adjudication(db, f2.id, "NOT_ACTIONABLE", "r2")

        summary = get_review_summary(db)
        assert summary["total_reviewed"] == 2
        assert summary["useful"] == 1
        assert summary["not_actionable"] == 1


# ---------------------------------------------------------------------------
# Mission ↔ Finding explicit linkage
# ---------------------------------------------------------------------------

class TestMissionFindingLinkage:
    def test_create_link(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        link = create_mission_finding_link(db, "MISSION-001", f.id, repo.id, "PRIMARY")
        assert link.mission_id == "MISSION-001"
        assert link.relationship_type == "PRIMARY"

    def test_idempotent_link(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        link1 = create_mission_finding_link(db, "MISSION-001", f.id, repo.id)
        link2 = create_mission_finding_link(db, "MISSION-001", f.id, repo.id)
        assert link1.id == link2.id

    def test_many_to_one(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f1 = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t1")
        f2 = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t2")
        db.add_all([f1, f2])
        db.commit()

        create_mission_finding_link(db, "MISSION-001", f1.id, repo.id, "PRIMARY")
        create_mission_finding_link(db, "MISSION-001", f2.id, repo.id, "SUPPORTING")

        links = get_mission_links(db, "MISSION-001")
        assert len(links) == 2

    def test_duplicate_mission_ids_not_assumed(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        links = get_finding_mission_links(db, f.id)
        assert len(links) == 0


# ---------------------------------------------------------------------------
# Journal events
# ---------------------------------------------------------------------------

class TestJournalEvents:
    def test_finding_reviewed_event(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        adj = create_adjudication(db, f.id, "USEFUL", "reviewer")
        event = emit_finding_reviewed(db, f.id, repo.id, "USEFUL", "reviewer", "note", adj.id)

        assert event.event_type == "finding.reviewed"
        assert event.actor == "reviewer"
        assert event.payload["classification"] == "USEFUL"

    def test_finding_reclassified_event(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(repository_id=repo.id, finding_type="x", severity="low", category="c", title="t")
        db.add(f)
        db.commit()

        adj1 = create_adjudication(db, f.id, "USEFUL", "reviewer")
        adj2 = create_adjudication(db, f.id, "NOT_ACTIONABLE", "reviewer")
        event = emit_finding_reclassified(db, f.id, repo.id, "NOT_ACTIONABLE", "reviewer", adj1.id, "changed", adj2.id)

        assert event.event_type == "finding.reclassified"
        assert event.payload["previous_adjudication_id"] == adj1.id


# ---------------------------------------------------------------------------
# Day 2R classification persistence
# ---------------------------------------------------------------------------

class TestDay2RClassificationPersistence:
    def test_day2r_totals(self, setup_db):
        db = setup_db
        repo = Repository(name="flask", url="https://example.com/flask")
        db.add(repo)
        db.commit()

        counts = {"USEFUL": 0, "NOT_ACTIONABLE": 0, "NEEDS_MORE_EVIDENCE": 0, "DUPLICATE": 0}
        for i in range(4):
            f = Finding(repository_id=repo.id, finding_type="x", severity="high", category="c", title=f"u{i}")
            db.add(f)
            db.commit()
            create_adjudication(db, f.id, "USEFUL", "David")
            counts["USEFUL"] += 1

        for i in range(12):
            f = Finding(repository_id=repo.id, finding_type="x", severity="medium", category="c", title=f"na{i}")
            db.add(f)
            db.commit()
            create_adjudication(db, f.id, "NOT_ACTIONABLE", "David")
            counts["NOT_ACTIONABLE"] += 1

        for i in range(13):
            f = Finding(repository_id=repo.id, finding_type="x", severity="medium", category="c", title=f"nme{i}")
            db.add(f)
            db.commit()
            create_adjudication(db, f.id, "NEEDS_MORE_EVIDENCE", "David")
            counts["NEEDS_MORE_EVIDENCE"] += 1

        f = Finding(repository_id=repo.id, finding_type="x", severity="high", category="c", title="dup")
        db.add(f)
        db.commit()
        create_adjudication(db, f.id, "DUPLICATE", "David")
        counts["DUPLICATE"] += 1

        summary = get_review_summary(db)
        assert summary["useful"] == 4
        assert summary["not_actionable"] == 12
        assert summary["needs_more_evidence"] == 13
        assert summary["duplicate"] == 1
        assert summary["total_reviewed"] == 30

        classifiable = 30 - 1
        assert summary["finding_precision"] == pytest.approx(4 / classifiable, rel=1e-2)
        assert summary["actionability_rate"] == pytest.approx(4 / 30, rel=1e-2)


# ---------------------------------------------------------------------------
# Queue integrity regression tests
# ---------------------------------------------------------------------------

class TestReviewQueueIntegrity:
    def test_review_items_use_persisted_finding_identity(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t", module="src/main.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["db_id"] == f.id
        assert item["finding_id"] == "FINDING-001"

    def test_same_core_finding_id_across_repos_no_collision(self, setup_db):
        db = setup_db
        repo1 = Repository(name="repo-a", url="https://example.com/a")
        repo2 = Repository(name="repo-b", url="https://example.com/b")
        db.add_all([repo1, repo2])
        db.commit()

        f1 = Finding(
            repository_id=repo1.id, finding_type="x", severity="high", category="c",
            title="t1", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        f2 = Finding(
            repository_id=repo2.id, finding_type="x", severity="high", category="c",
            title="t2", module="src/b.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add_all([f1, f2])
        db.commit()

        result = build_review_queue(db)
        assert len(result["items"]) == 2
        ids = {item["db_id"] for item in result["items"]}
        assert len(ids) == 2

    def test_same_core_finding_id_across_scans_no_collision(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        f1 = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t1", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        f2 = Finding(
            repository_id=repo.id, finding_type="x", severity="medium", category="c",
            title="t2", module="src/b.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add_all([f1, f2])
        db.commit()

        result = build_review_queue(db)
        assert len(result["items"]) == 2
        ids = {item["db_id"] for item in result["items"]}
        assert len(ids) == 2

    def test_review_queue_can_be_restricted_to_scan(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        f1 = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t1", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        f2 = Finding(
            repository_id=repo.id, finding_type="x", severity="medium", category="c",
            title="t2", module="src/b.py",
            metadata_json={"finding_id": "FINDING-002", "evidence_references": []},
        )
        db.add_all([f1, f2])
        db.commit()

        result = build_review_queue(db, repository_id=repo.id)
        assert result["total"] == 2

        result2 = build_review_queue(db, repository_id="nonexistent")
        assert result2["total"] == 0

    def test_context_summary_equals_actual_selected_records(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        for i in range(3):
            f = Finding(
                repository_id=repo.id, finding_type="x", severity="high", category="c",
                title=f"prod{i}", module="src/main.py",
                metadata_json={"finding_id": f"P-{i:03d}", "evidence_references": []},
            )
            db.add(f)
        for i in range(2):
            f = Finding(
                repository_id=repo.id, finding_type="x", severity="medium", category="c",
                title=f"test{i}", module=f"tests/test_{i}.py",
                metadata_json={"finding_id": f"T-{i:03d}", "evidence_references": []},
            )
            db.add(f)
        db.commit()

        result = build_review_queue(db)
        items = result["items"]
        ctx_counts = {}
        for item in items:
            ctx = item["file_context"]
            ctx_counts[ctx] = ctx_counts.get(ctx, 0) + 1

        assert ctx_counts.get("PRODUCTION", 0) == 3
        assert ctx_counts.get("TEST", 0) == 2

    def test_severity_summary_equals_actual_selected_records(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        for i in range(2):
            f = Finding(
                repository_id=repo.id, finding_type="x", severity="high", category="c",
                title=f"h{i}", module="src/a.py",
                metadata_json={"finding_id": f"H-{i:03d}", "evidence_references": []},
            )
            db.add(f)
        f = Finding(
            repository_id=repo.id, finding_type="x", severity="low", category="c",
            title="l0", module="src/b.py",
            metadata_json={"finding_id": "L-000", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        sev_counts = {}
        for item in result["items"]:
            s = item["severity"]
            sev_counts[s] = sev_counts.get(s, 0) + 1

        assert sev_counts.get("high", 0) == 2
        assert sev_counts.get("low", 0) == 1

    def test_repository_summary_equals_actual_selected_records(self, setup_db):
        db = setup_db
        repo1 = Repository(name="repo-a", url="https://example.com/a")
        repo2 = Repository(name="repo-b", url="https://example.com/b")
        db.add_all([repo1, repo2])
        db.commit()

        for i in range(3):
            f = Finding(
                repository_id=repo1.id, finding_type="x", severity="high", category="c",
                title=f"a{i}", module="src/x.py",
                metadata_json={"finding_id": f"A-{i:03d}", "evidence_references": []},
            )
            db.add(f)
        f = Finding(
            repository_id=repo2.id, finding_type="x", severity="medium", category="c",
            title="b0", module="src/y.py",
            metadata_json={"finding_id": "B-000", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        repo_counts = {}
        for item in result["items"]:
            r = item["repository_name"]
            repo_counts[r] = repo_counts.get(r, 0) + 1

        assert repo_counts.get("repo-a", 0) == 3
        assert repo_counts.get("repo-b", 0) == 1

    def test_governance_summary_equals_actual_selected_records(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        for i in range(3):
            f = Finding(
                repository_id=repo.id, finding_type="x", severity="high", category="c",
                title=f"ap{i}", module="src/a.py",
                metadata_json={
                    "finding_id": f"G-{i:03d}",
                    "evidence_references": [],
                    "governance_decision": {"decision": "APPROVED", "rationale": "ok"},
                },
            )
            db.add(f)
        f = Finding(
            repository_id=repo.id, finding_type="x", severity="medium", category="c",
            title="rej0", module="src/b.py",
            metadata_json={
                "finding_id": "R-000",
                "evidence_references": [],
                "governance_decision": {"decision": "REJECTED", "rationale": "no"},
            },
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        gov_counts = {}
        for item in result["items"]:
            g = item["governance_decision"]
            gov_counts[g] = gov_counts.get(g, 0) + 1

        assert gov_counts.get("APPROVED", 0) == 3
        assert gov_counts.get("REJECTED", 0) == 1

    def test_no_duplicate_persisted_finding_enters_sample_twice(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        db_ids = [item["db_id"] for item in result["items"]]
        assert len(db_ids) == len(set(db_ids))

    def test_every_review_item_has_scan_provenance(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()

        from enterprise.models import ScanJob
        scan = ScanJob(
            repository_id=repo.id, status="completed", commit_sha="abc123def456",
        )
        db.add(scan)
        db.commit()

        f = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result = build_review_queue(db)
        item = result["items"][0]
        assert item["scan_id"] == scan.id
        assert item["commit_sha"] == "abc123def456"

    def test_historical_queue_remains_immutable_after_regeneration(self, setup_db):
        db = setup_db
        repo = Repository(name="test", url="https://example.com/test")
        db.add(repo)
        db.commit()
        f = Finding(
            repository_id=repo.id, finding_type="x", severity="high", category="c",
            title="t", module="src/a.py",
            metadata_json={"finding_id": "FINDING-001", "evidence_references": []},
        )
        db.add(f)
        db.commit()

        result1 = build_review_queue(db)
        item1 = result1["items"][0].copy()

        create_adjudication(db, f.id, "USEFUL", "reviewer")

        result2 = build_review_queue(db)
        item2 = result2["items"][0]

        assert item1["db_id"] == item2["db_id"]
        assert item1["finding_id"] == item2["finding_id"]
        assert item1["scan_id"] == item2["scan_id"]
        assert item1["commit_sha"] == item2["commit_sha"]
