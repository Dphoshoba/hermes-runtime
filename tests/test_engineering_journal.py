"""Tests for Engineering Journal v1.0 — comprehensive coverage.

Covers:
- JournalEvent model: creation, serialization, roundtrip, integrity verification
- JournalStore: append, immutability, query, ordering, persistence, concurrent access
- JournalEmitter: all pipeline stage emitters
- OvernightSummary: generation, filtering, determinism
- CLI: all commands
- Integration: end-to-end pipeline observability
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evosia.journal_models import (
    JournalEvent,
    create_event,
    _canonical_payload_sha256,
    _format_utc,
    EVENT_TYPES,
    STAGE_CATEGORIES,
)
from evosia.journal_store import JournalStore
from evosia.journal_emitter import JournalEmitter
from evosia.journal_summary import (
    OvernightSummary,
    StageSummary,
    generate_overnight_summary,
)


# ---------------------------------------------------------------------------
# Deterministic clock
# ---------------------------------------------------------------------------

class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._step = timedelta(seconds=1)

    def __call__(self) -> datetime:
        value = self.current
        self.current += self._step
        return value


# ---------------------------------------------------------------------------
# JournalEvent model tests
# ---------------------------------------------------------------------------

class TestJournalEvent:
    def test_create_event_basic(self):
        clock = Clock()
        event = create_event("readiness.assessed", {"status": "ready"}, clock=clock)
        assert event.event_type == "readiness.assessed"
        assert event.stage == "readiness"
        assert event.payload == {"status": "ready"}
        assert event.actor == "system"
        assert event.event_id
        assert event.timestamp.startswith("2026-01-01")

    def test_create_event_with_repository(self):
        clock = Clock()
        event = create_event(
            "repo.scanned",
            {"modules": 10},
            repository="owner/repo",
            clock=clock,
        )
        assert event.repository == "owner/repo"

    def test_create_event_with_actor(self):
        clock = Clock()
        event = create_event(
            "mission.completed",
            {"tasks": 5},
            actor="operator@company.com",
            clock=clock,
        )
        assert event.actor == "operator@company.com"

    def test_create_event_with_metadata(self):
        clock = Clock()
        event = create_event(
            "evidence.recorded",
            {"hash": "abc"},
            metadata={"trace_id": "trace-123"},
            clock=clock,
        )
        assert event.metadata == {"trace_id": "trace-123"}

    def test_create_event_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown event type"):
            create_event("invalid.type", {})

    def test_event_id_deterministic(self):
        fixed = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        clock = Clock(start=fixed)
        e1 = create_event("readiness.assessed", {"x": 1}, clock=clock)
        # Reset clock to same instant
        clock.current = fixed
        e2 = create_event("readiness.assessed", {"x": 1}, clock=clock)
        assert e1.event_id == e2.event_id

    def test_event_id_differs_for_different_payload(self):
        clock = Clock()
        e1 = create_event("readiness.assessed", {"x": 1}, clock=clock)
        e2 = create_event("readiness.assessed", {"x": 2}, clock=clock)
        assert e1.event_id != e2.event_id

    def test_event_id_differs_for_different_types(self):
        clock = Clock()
        e1 = create_event("readiness.assessed", {"x": 1}, clock=clock)
        e2 = create_event("repo.scanned", {"x": 1}, clock=clock)
        assert e1.event_id != e2.event_id

    def test_as_dict_roundtrip(self):
        clock = Clock()
        event = create_event(
            "mission.completed",
            {"tasks": 5, "status": "ok"},
            repository="owner/repo",
            actor="system",
            metadata={"key": "value"},
            clock=clock,
        )
        d = event.as_dict()
        restored = JournalEvent.from_dict(d)
        assert restored == event
        assert restored.as_dict() == d

    def test_verify_integrity_valid(self):
        clock = Clock()
        event = create_event("readiness.assessed", {"x": 1}, clock=clock)
        assert event.verify_integrity() is True

    def test_verify_integrity_tampered_payload(self):
        clock = Clock()
        event = create_event("readiness.assessed", {"x": 1}, clock=clock)
        tampered = JournalEvent(
            event_id=event.event_id,
            timestamp=event.timestamp,
            event_type=event.event_type,
            stage=event.stage,
            repository=event.repository,
            actor=event.actor,
            payload={"x": 2},  # modified
            payload_sha256=event.payload_sha256,  # original hash
        )
        assert tampered.verify_integrity() is False

    def test_stage_assignment(self):
        clock = Clock()
        for etype, expected_stage in STAGE_CATEGORIES.items():
            event = create_event(etype, {}, clock=clock)
            assert event.stage == expected_stage

    def test_all_event_types_defined(self):
        # Verify the actual registry contract: every registered event type must
        # have a stage category, and the five Evidence & Risk Gate events must
        # be present (31 total: 26 historical + 5 gate events).
        EXPECTED_GATE_EVENTS = {
            "gate.evaluated",
            "gate.routed",
            "human.adjudication",
            "policy.suppression",
            "mission.eligibility",
        }
        assert len(EVENT_TYPES) == 31
        for et in EVENT_TYPES:
            assert et in STAGE_CATEGORIES, f"event {et!r} missing stage category"
        for ge in EXPECTED_GATE_EVENTS:
            assert ge in EVENT_TYPES, f"gate event {ge!r} not registered"
        # Historical event types must remain unchanged.
        assert "readiness.assessed" in EVENT_TYPES
        assert "mission.completed" in EVENT_TYPES
        assert "github.materialized" in EVENT_TYPES

    def test_payload_sha256_deterministic(self):
        payload = {"a": 1, "b": [2, 3]}
        h1 = _canonical_payload_sha256(payload)
        h2 = _canonical_payload_sha256(payload)
        assert h1 == h2

    def test_payload_sha256_differs_for_different_data(self):
        h1 = _canonical_payload_sha256({"a": 1})
        h2 = _canonical_payload_sha256({"a": 2})
        assert h1 != h2

    def test_empty_payload(self):
        clock = Clock()
        event = create_event("health.checked", {}, clock=clock)
        assert event.payload == {}
        assert event.verify_integrity() is True

    def test_nested_payload(self):
        clock = Clock()
        payload = {"level1": {"level2": [1, 2, {"level3": True}]}}
        event = create_event("github.metadata_fetched", payload, clock=clock)
        assert event.verify_integrity() is True
        d = event.as_dict()
        assert d["payload"] == payload


# ---------------------------------------------------------------------------
# JournalStore tests
# ---------------------------------------------------------------------------

class TestJournalStore:
    def test_open_creates_directories(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()
        assert journal_dir.exists()
        assert (journal_dir / "events").exists()
        store.close()

    def test_append_and_retrieve(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        event = create_event("readiness.assessed", {"status": "ready"}, clock=clock)
        store.append(event)

        retrieved = store.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id
        store.close()

    def test_append_duplicate_raises(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        event = create_event("readiness.assessed", {"status": "ready"}, clock=clock)
        store.append(event)

        with pytest.raises(ValueError, match="Duplicate event_id"):
            store.append(event)
        store.close()

    def test_append_many(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        events = [
            create_event("readiness.assessed", {"i": i}, clock=clock)
            for i in range(5)
        ]
        store.append_many(events)
        assert store.count_events() == 5
        store.close()

    def test_append_many_duplicate_raises(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        event = create_event("readiness.assessed", {"i": 0}, clock=clock)
        store.append(event)

        with pytest.raises(ValueError, match="Duplicate event_id"):
            store.append_many([event])
        store.close()

    def test_list_events_filter_by_type(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {"a": 1}, clock=clock))
        store.append(create_event("repo.scanned", {"b": 2}, clock=clock))
        store.append(create_event("readiness.assessed", {"c": 3}, clock=clock))

        events = store.list_events(event_type="readiness.assessed")
        assert len(events) == 2
        assert all(e.event_type == "readiness.assessed" for e in events)
        store.close()

    def test_list_events_filter_by_stage(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {}, clock=clock))
        store.append(create_event("repo.scanned", {}, clock=clock))
        store.append(create_event("repo.analyzed", {}, clock=clock))

        events = store.list_events(stage="repository_intelligence")
        assert len(events) == 2
        store.close()

    def test_list_events_filter_by_repository(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {}, repository="a/b", clock=clock))
        store.append(create_event("readiness.assessed", {}, repository="c/d", clock=clock))

        events = store.list_events(repository="a/b")
        assert len(events) == 1
        assert events[0].repository == "a/b"
        store.close()

    def test_list_events_filter_by_actor(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {}, actor="alice", clock=clock))
        store.append(create_event("readiness.assessed", {}, actor="bob", clock=clock))

        events = store.list_events(actor="alice")
        assert len(events) == 1
        store.close()

    def test_list_events_after_before(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock(start=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        e1 = create_event("readiness.assessed", {"i": 1}, clock=clock)
        store.append(e1)
        e2 = create_event("readiness.assessed", {"i": 2}, clock=clock)
        store.append(e2)
        e3 = create_event("readiness.assessed", {"i": 3}, clock=clock)
        store.append(e3)

        # Filter: only events after e1's timestamp
        events = store.list_events(after=e1.timestamp)
        assert len(events) == 2

        # Filter: only events before e3's timestamp
        events = store.list_events(before=e3.timestamp)
        assert len(events) == 2

        # Filter: between e1 and e3
        events = store.list_events(after=e1.timestamp, before=e3.timestamp)
        assert len(events) == 1
        assert events[0].event_id == e2.event_id
        store.close()

    def test_list_events_limit(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        for i in range(10):
            store.append(create_event("readiness.assessed", {"i": i}, clock=clock))

        events = store.list_events(limit=3)
        assert len(events) == 3
        store.close()

    def test_deterministic_ordering(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        events_in = []
        for i in range(5):
            ev = create_event("readiness.assessed", {"i": i}, clock=clock)
            events_in.append(ev)
            store.append(ev)

        events_out = store.list_events()
        assert [e.event_id for e in events_out] == [e.event_id for e in events_in]
        store.close()

    def test_persistence_across_sessions(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        clock = Clock()

        # Session 1: write events
        store1 = JournalStore(journal_dir)
        store1.open()
        ev1 = create_event("readiness.assessed", {"a": 1}, clock=clock)
        ev2 = create_event("repo.scanned", {"b": 2}, clock=clock)
        store1.append(ev1)
        store1.append(ev2)
        store1.close()

        # Session 2: read events
        store2 = JournalStore(journal_dir)
        store2.open()
        assert store2.count_events() == 2
        assert store2.get_event(ev1.event_id) is not None
        assert store2.get_event(ev2.event_id) is not None
        store2.close()

    def test_verify_integrity(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {"a": 1}, clock=clock))
        store.append(create_event("repo.scanned", {"b": 2}, clock=clock))

        errors = store.verify_integrity()
        assert errors == []
        store.close()

    def test_count_events(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {}, clock=clock))
        store.append(create_event("repo.scanned", {}, clock=clock))
        store.append(create_event("readiness.assessed", {}, clock=clock))

        assert store.count_events() == 3
        assert store.count_events(event_type="readiness.assessed") == 2
        assert store.count_events(event_type="repo.scanned") == 1
        store.close()

    def test_events_iterator(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        ids = []
        for i in range(5):
            ev = create_event("readiness.assessed", {"i": i}, clock=clock)
            store.append(ev)
            ids.append(ev.event_id)

        collected = [e.event_id for e in store.events_iterator()]
        assert collected == ids
        store.close()

    def test_as_dict(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        store.append(create_event("readiness.assessed", {"a": 1}, clock=clock))

        d = store.as_dict()
        assert d["schema_version"] == "1.0"
        assert d["event_count"] == 1
        assert len(d["events"]) == 1
        store.close()

    def test_empty_store_queries(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        assert store.count_events() == 0
        assert store.list_events() == []
        assert store.get_event("nonexistent") is None
        assert store.verify_integrity() == []
        store.close()

    def test_context_manager(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        with JournalStore(journal_dir) as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {}, clock=clock))
            assert store.count_events() == 1

    def test_operations_without_open_raise(self, tmp_path: Path):
        store = JournalStore(tmp_path / "journal")
        with pytest.raises(RuntimeError, match="not open"):
            store.list_events()


# ---------------------------------------------------------------------------
# JournalStore concurrent access tests
# ---------------------------------------------------------------------------

class TestJournalStoreConcurrency:
    def test_concurrent_appends(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        errors = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(5):
                    clock = Clock()
                    event = create_event(
                        "readiness.assessed",
                        {"thread": thread_id, "i": i},
                        clock=clock,
                    )
                    store.append(event)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert store.count_events() == 15
        store.close()

    def test_concurrent_reads(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        store = JournalStore(journal_dir)
        store.open()

        clock = Clock()
        for i in range(10):
            store.append(create_event("readiness.assessed", {"i": i}, clock=clock))

        results = []

        def reader() -> None:
            events = store.list_events()
            results.append(len(events))

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 10 for r in results)
        store.close()


# ---------------------------------------------------------------------------
# JournalEmitter tests
# ---------------------------------------------------------------------------

class TestJournalEmitter:
    def test_emit_readiness_assessed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_readiness_assessed(
                {"status": "ready", "confidence": 0.9},
                repository="owner/repo",
            )
            assert event.event_type == "readiness.assessed"
            assert event.repository == "owner/repo"
            assert store.count_events() == 1

    def test_emit_readiness_blocked(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_readiness_blocked(
                {"reasons": ["merge_conflicts"]},
                repository="owner/repo",
            )
            assert event.event_type == "readiness.blocked"

    def test_emit_repo_scanned(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_repo_scanned(
                {"modules": 42, "files": 100},
                repository="owner/repo",
            )
            assert event.event_type == "repo.scanned"

    def test_emit_repo_analyzed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_repo_analyzed(
                {"health_score": 85.0},
                repository="owner/repo",
            )
            assert event.event_type == "repo.analyzed"

    def test_emit_engineering_analyzed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_engineering_analyzed(
                {"findings": 12, "health_score": 72.0},
                repository="owner/repo",
            )
            assert event.event_type == "engineering.analyzed"

    def test_emit_governance_decided(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_governance_decided(
                {"approved": 5, "deferred": 2},
                repository="owner/repo",
            )
            assert event.event_type == "governance.decided"

    def test_emit_recommendation_generated(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_recommendation_generated(
                {"missions": 3},
                repository="owner/repo",
            )
            assert event.event_type == "recommendation.generated"

    def test_emit_recommendation_approved(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_recommendation_approved(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )
            assert event.event_type == "recommendation.approved"

    def test_emit_recommendation_rejected(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_recommendation_rejected(
                {"mission_id": "m-002", "reason": "too risky"},
                repository="owner/repo",
            )
            assert event.event_type == "recommendation.rejected"

    def test_emit_mission_created(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_created(
                {"mission_id": "m-001", "tasks": 3},
                repository="owner/repo",
            )
            assert event.event_type == "mission.created"

    def test_emit_mission_planned(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_planned(
                {"plan_hash": "abc123", "valid": True},
                repository="owner/repo",
            )
            assert event.event_type == "mission.planned"

    def test_emit_mission_started(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_started(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.started"

    def test_emit_mission_completed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_completed(
                {"mission_id": "m-001", "tasks_completed": 5},
                repository="owner/repo",
            )
            assert event.event_type == "mission.completed"

    def test_emit_mission_failed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_failed(
                {"mission_id": "m-001", "error": "timeout"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.failed"

    def test_emit_mission_cancelled(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_cancelled(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.cancelled"

    def test_emit_mission_aborted(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_aborted(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.aborted"

    def test_emit_mission_paused(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_paused(
                {"mission_id": "m-001", "reason": "manual"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.paused"

    def test_emit_mission_resumed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_mission_resumed(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )
            assert event.event_type == "mission.resumed"

    def test_emit_evidence_recorded(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_evidence_recorded(
                {"execution_id": "exec-001", "artifacts": 3},
                repository="owner/repo",
            )
            assert event.event_type == "evidence.recorded"

    def test_emit_review_completed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_review_completed(
                {"outcome": "REVIEW_PASSED", "checks": 10},
                repository="owner/repo",
            )
            assert event.event_type == "review.completed"

    def test_emit_health_checked(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_health_checked(
                {"overall_health": "HEALTHY"},
                repository="owner/repo",
            )
            assert event.event_type == "health.checked"

    def test_emit_github_metadata_fetched(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_github_metadata_fetched(
                {"name": "repo", "visibility": "public"},
                repository="owner/repo",
            )
            assert event.event_type == "github.metadata_fetched"

    def test_emit_github_branches_listed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_github_branches_listed(
                {"branches": ["main", "develop"]},
                repository="owner/repo",
            )
            assert event.event_type == "github.branches_listed"

    def test_emit_github_pr_listed(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_github_pr_listed(
                {"pull_requests": 3},
                repository="owner/repo",
            )
            assert event.event_type == "github.pr_listed"

    def test_emit_github_actions_checked(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_github_actions_checked(
                {"runs": 5, "passing": 4},
                repository="owner/repo",
            )
            assert event.event_type == "github.actions_checked"

    def test_emit_github_materialized(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store)
            event = emitter.emit_github_materialized(
                {"path": "/tmp/repo", "depth": 1},
                repository="owner/repo",
            )
            assert event.event_type == "github.materialized"

    def test_emitter_custom_actor(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store, actor="custom-actor")
            event = emitter.emit_readiness_assessed({"status": "ok"})
            assert event.actor == "custom-actor"

    def test_emitter_all_events_stored(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store, clock=Clock())
            emitter.emit_readiness_assessed({})
            emitter.emit_repo_scanned({})
            emitter.emit_engineering_analyzed({})
            emitter.emit_governance_decided({})
            emitter.emit_mission_completed({})
            emitter.emit_evidence_recorded({})
            emitter.emit_review_completed({})
            emitter.emit_health_checked({})
            emitter.emit_github_metadata_fetched({})
            assert store.count_events() == 9


# ---------------------------------------------------------------------------
# OvernightSummary tests
# ---------------------------------------------------------------------------

class TestOvernightSummary:
    def test_empty_journal_summary(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            summary = generate_overnight_summary(store)
            assert summary.total_events == 0
            assert summary.event_type_counts == {}
            assert summary.stage_summaries == ()
            assert summary.repositories == ()

    def test_summary_basic(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {"a": 1}, repository="a/b", clock=clock))
            store.append(create_event("repo.scanned", {"b": 2}, repository="a/b", clock=clock))
            store.append(create_event("engineering.analyzed", {"c": 3}, repository="c/d", clock=clock))

            summary = generate_overnight_summary(store)
            assert summary.total_events == 3
            assert summary.event_type_counts["readiness.assessed"] == 1
            assert summary.event_type_counts["repo.scanned"] == 1
            assert summary.event_type_counts["engineering.analyzed"] == 1
            assert set(summary.repositories) == {"a/b", "c/d"}

    def test_summary_stage_aggregation(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {}, clock=clock))
            store.append(create_event("readiness.blocked", {}, clock=clock))
            store.append(create_event("repo.scanned", {}, clock=clock))

            summary = generate_overnight_summary(store)
            stages = {s.stage: s for s in summary.stage_summaries}
            assert stages["readiness"].event_count == 2
            assert stages["repository_intelligence"].event_count == 1

    def test_summary_filter_after(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            e1 = create_event("readiness.assessed", {"i": 1}, clock=clock)
            store.append(e1)
            e2 = create_event("repo.scanned", {"i": 2}, clock=clock)
            store.append(e2)

            summary = generate_overnight_summary(store, after=e1.timestamp)
            assert summary.total_events == 1

    def test_summary_filter_before(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            e1 = create_event("readiness.assessed", {"i": 1}, clock=clock)
            store.append(e1)
            e2 = create_event("repo.scanned", {"i": 2}, clock=clock)
            store.append(e2)

            summary = generate_overnight_summary(store, before=e2.timestamp)
            assert summary.total_events == 1

    def test_summary_deterministic(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {"a": 1}, clock=clock))
            store.append(create_event("repo.scanned", {"b": 2}, clock=clock))

            s1 = generate_overnight_summary(store, generated_at="2026-01-01T00:00:00.000000Z")
            s2 = generate_overnight_summary(store, generated_at="2026-01-01T00:00:00.000000Z")
            assert s1.as_dict() == s2.as_dict()

    def test_summary_as_dict_roundtrip(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {"a": 1}, clock=clock))

            summary = generate_overnight_summary(store, generated_at="2026-01-01T00:00:00.000000Z")
            d = summary.as_dict()
            assert d["schema_version"] == "1.0"
            assert d["total_events"] == 1

    def test_summary_render_markdown(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {}, repository="a/b", clock=clock))
            store.append(create_event("repo.scanned", {}, repository="a/b", clock=clock))

            summary = generate_overnight_summary(store, generated_at="2026-01-01T00:00:00.000000Z")
            md = summary.render_markdown()
            assert "# Engineering Journal" in md
            assert "Total Events" in md
            assert "readiness" in md

    def test_summary_markdown_empty(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            summary = generate_overnight_summary(store, generated_at="2026-01-01T00:00:00.000000Z")
            md = summary.render_markdown()
            assert "# Engineering Journal" in md
            assert "Total Events:** 0" in md

    def test_summary_actors(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            store.append(create_event("readiness.assessed", {}, actor="alice", clock=clock))
            store.append(create_event("repo.scanned", {}, actor="bob", clock=clock))

            summary = generate_overnight_summary(store)
            assert "alice" in summary.actors
            assert "bob" in summary.actors

    def test_summary_event_ids(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            e1 = create_event("readiness.assessed", {}, clock=clock)
            e2 = create_event("repo.scanned", {}, clock=clock)
            store.append(e1)
            store.append(e2)

            summary = generate_overnight_summary(store)
            assert e1.event_id in summary.event_ids
            assert e2.event_id in summary.event_ids

    def test_summary_timestamps(self, tmp_path: Path):
        with JournalStore(tmp_path / "journal") as store:
            clock = Clock()
            e1 = create_event("readiness.assessed", {}, clock=clock)
            store.append(e1)
            e2 = create_event("repo.scanned", {}, clock=clock)
            store.append(e2)

            summary = generate_overnight_summary(store)
            assert summary.first_event_timestamp == e1.timestamp
            assert summary.last_event_timestamp == e2.timestamp


# ---------------------------------------------------------------------------
# StageSummary tests
# ---------------------------------------------------------------------------

class TestStageSummary:
    def test_as_dict(self):
        s = StageSummary(
            stage="readiness",
            event_count=2,
            event_types=("readiness.assessed", "readiness.blocked"),
            repositories=("a/b",),
        )
        d = s.as_dict()
        assert d["stage"] == "readiness"
        assert d["event_count"] == 2
        assert len(d["event_types"]) == 2
        assert d["repositories"] == ["a/b"]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _run_journal(self, args: list[str], repo: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python", "-m", "evosia.journal_cli", "--repo", repo] + args,
            capture_output=True,
            text=True,
        )

    def test_record_and_list(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"status":"ok"}'],
            repo,
        )
        assert result.returncode == 0

        result = self._run_journal(["list"], repo)
        assert result.returncode == 0
        assert "readiness.assessed" in result.stdout

    def test_list_json(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )

        result = self._run_journal(["list", "--json"], repo)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["event_type"] == "readiness.assessed"

    def test_record_with_repository(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(
            ["record", "repo.scanned", "--payload", '{"m":1}', "--repository", "owner/repo"],
            repo,
        )
        assert result.returncode == 0

        result = self._run_journal(["list", "--json"], repo)
        data = json.loads(result.stdout)
        assert data[0]["repository"] == "owner/repo"

    def test_show_event(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"x":1}'],
            repo,
        )
        event_id = json.loads(result.stdout)["event_id"]

        result = self._run_journal(["show", event_id], repo)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["event_id"] == event_id

    def test_show_nonexistent(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(["show", "nonexistent"], repo)
        assert result.returncode == 1

    def test_summary(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )

        result = self._run_journal(["summary"], repo)
        assert result.returncode == 0
        assert "Engineering Journal" in result.stdout

    def test_summary_json(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )

        result = self._run_journal(["summary", "--json"], repo)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_events"] == 1

    def test_integrity(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )

        result = self._run_journal(["integrity"], repo)
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_integrity_json(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )

        result = self._run_journal(["integrity", "--json"], repo)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    def test_types(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(["types"], repo)
        assert result.returncode == 0
        assert "readiness.assessed" in result.stdout

    def test_types_json(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        result = self._run_journal(["types", "--json"], repo)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "readiness.assessed" in data

    def test_export(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}'],
            repo,
        )
        self._run_journal(
            ["record", "repo.scanned", "--payload", '{"b":2}'],
            repo,
        )

        result = self._run_journal(["export"], repo)
        assert result.returncode == 0
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) == 2

    def test_list_with_filters(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        self._run_journal(
            ["record", "readiness.assessed", "--payload", '{"a":1}', "--repository", "a/b"],
            repo,
        )
        self._run_journal(
            ["record", "repo.scanned", "--payload", '{"b":2}', "--repository", "c/d"],
            repo,
        )

        result = self._run_journal(["list", "--type", "readiness.assessed"], repo)
        assert result.returncode == 0
        assert "readiness.assessed" in result.stdout
        assert "repo.scanned" not in result.stdout

    def test_list_with_limit(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        for i in range(5):
            self._run_journal(
                ["record", "readiness.assessed", "--payload", f'{{"i":{i}}}'],
                repo,
            )

        result = self._run_journal(["list", "--limit", "2"], repo)
        assert result.returncode == 0
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) == 2

    def test_record_stdin(self, tmp_path: Path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)

        proc = subprocess.run(
            ["python", "-m", "evosia.journal_cli", "--repo", repo,
             "record", "readiness.assessed"],
            input='{"from_stdin": true}',
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0

        result = self._run_journal(["list", "--json"], repo)
        data = json.loads(result.stdout)
        assert data[0]["payload"]["from_stdin"] is True


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_observability(self, tmp_path: Path):
        """Simulate a full pipeline run and verify all events are recorded."""
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store, clock=Clock())

            # Readiness
            emitter.emit_readiness_assessed(
                {"status": "ready", "confidence": 0.9},
                repository="owner/repo",
            )

            # Repo Intelligence
            emitter.emit_repo_scanned(
                {"modules": 42, "files": 100},
                repository="owner/repo",
            )
            emitter.emit_repo_analyzed(
                {"health_score": 85.0},
                repository="owner/repo",
            )

            # Engineering Intelligence
            emitter.emit_engineering_analyzed(
                {"findings": 12, "health_score": 72.0},
                repository="owner/repo",
            )

            # Governance
            emitter.emit_governance_decided(
                {"approved": 5, "deferred": 2},
                repository="owner/repo",
            )

            # Recommendation
            emitter.emit_recommendation_generated(
                {"missions": 3},
                repository="owner/repo",
            )
            emitter.emit_recommendation_approved(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )

            # Mission
            emitter.emit_mission_created(
                {"mission_id": "m-001", "tasks": 3},
                repository="owner/repo",
            )
            emitter.emit_mission_planned(
                {"plan_hash": "abc123", "valid": True},
                repository="owner/repo",
            )
            emitter.emit_mission_started(
                {"mission_id": "m-001"},
                repository="owner/repo",
            )

            # Evidence
            emitter.emit_evidence_recorded(
                {"execution_id": "exec-001", "artifacts": 3},
                repository="owner/repo",
            )

            # Review
            emitter.emit_review_completed(
                {"outcome": "REVIEW_PASSED", "checks": 10},
                repository="owner/repo",
            )

            # Health
            emitter.emit_health_checked(
                {"overall_health": "HEALTHY"},
                repository="owner/repo",
            )

            # Mission complete
            emitter.emit_mission_completed(
                {"mission_id": "m-001", "tasks_completed": 3},
                repository="owner/repo",
            )

            assert store.count_events() == 14

            # Verify integrity
            errors = store.verify_integrity()
            assert errors == []

            # Verify summary
            summary = generate_overnight_summary(store)
            assert summary.total_events == 14
            assert "owner/repo" in summary.repositories

    def test_multi_repository_journal(self, tmp_path: Path):
        """Multiple repositories in the same journal."""
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store, clock=Clock())

            emitter.emit_readiness_assessed({}, repository="org/repo-a")
            emitter.emit_readiness_assessed({}, repository="org/repo-b")
            emitter.emit_readiness_assessed({}, repository="org/repo-c")

            # Query per-repository
            events_a = store.list_events(repository="org/repo-a")
            assert len(events_a) == 1

            # Query all
            assert store.count_events() == 3

            # Summary
            summary = generate_overnight_summary(store)
            assert len(summary.repositories) == 3

    def test_event_type_coverage(self, tmp_path: Path):
        """Every defined event type can be emitted and stored."""
        with JournalStore(tmp_path / "journal") as store:
            emitter = JournalEmitter(store, clock=Clock())

            for etype in EVENT_TYPES:
                # Map event type to emitter method
                method_name = "emit_" + etype.replace(".", "_")
                method = getattr(emitter, method_name)
                method({"event_type": etype})

            assert store.count_events() == len(EVENT_TYPES)

            # All stored events verify integrity
            errors = store.verify_integrity()
            assert errors == []
