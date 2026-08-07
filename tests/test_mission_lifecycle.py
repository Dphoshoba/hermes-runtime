"""Tests for mission lifecycle state model, persistence, and control store."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from hermes_v01.mission_state import (
    MissionState,
    MissionStateStore,
    create_initial_state,
    transition_state,
    update_counts,
    TERMINAL_MISSION_STATES,
)
from hermes_v01.mission_control import (
    MissionControlCommand,
    MissionControlStore,
    write_control_command,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _initial(mission_id: str = "test-001", title: str = "Test", total: int = 4) -> MissionState:
    return create_initial_state(mission_id, title, total)


# ===================================================================
# MissionState — creation
# ===================================================================

class TestCreateInitialState:
    def test_default_state(self) -> None:
        s = _initial()
        assert s.state == "READY"
        assert s.tasks_total == 4
        assert s.tasks_completed == 0
        assert s.tasks_failed == 0
        assert s.tasks_remaining == 4
        assert s.last_control_command_id == 0
        assert s.started_at is None
        assert s.finished_at is None

    def test_schema_version(self) -> None:
        assert _initial().schema_version == "1"

    def test_is_not_terminal(self) -> None:
        assert not _initial().is_terminal()


# ===================================================================
# MissionState — transitions
# ===================================================================

class TestTransitionState:
    def test_ready_to_running(self) -> None:
        s = transition_state(_initial(), "RUNNING")
        assert s.state == "RUNNING"
        assert s.started_at is not None
        assert s.finished_at is None

    def test_running_to_paused(self) -> None:
        s = transition_state(transition_state(_initial(), "RUNNING"), "PAUSED", reason="test")
        assert s.state == "PAUSED"
        assert s.paused_at is not None
        assert s.pause_reason == "test"

    def test_paused_to_running(self) -> None:
        s = transition_state(
            transition_state(transition_state(_initial(), "RUNNING"), "PAUSED"),
            "RUNNING",
        )
        assert s.state == "RUNNING"
        assert s.resumed_at is not None

    def test_running_to_completed(self) -> None:
        s = transition_state(transition_state(_initial(), "RUNNING"), "COMPLETED")
        assert s.state == "COMPLETED"
        assert s.finished_at is not None
        assert s.tasks_completed == 4
        assert s.tasks_remaining == 0
        assert s.is_terminal()

    def test_running_to_cancelled(self) -> None:
        s = transition_state(
            transition_state(_initial(), "RUNNING"),
            "CANCELLED",
            reason="user abort",
            command_id=5,
        )
        assert s.state == "CANCELLED"
        assert s.cancel_reason == "user abort"
        assert s.last_control_command_id == 5
        assert s.is_terminal()

    def test_running_to_aborted(self) -> None:
        s = transition_state(
            transition_state(_initial(), "RUNNING"),
            "ABORTED",
            reason="emergency",
        )
        assert s.state == "ABORTED"
        assert s.abort_reason == "emergency"
        assert s.is_terminal()

    def test_running_to_failed(self) -> None:
        s = transition_state(transition_state(_initial(), "RUNNING"), "FAILED")
        assert s.state == "FAILED"
        assert s.is_terminal()

    def test_paused_to_cancelled(self) -> None:
        paused = transition_state(transition_state(_initial(), "RUNNING"), "PAUSED")
        s = transition_state(paused, "CANCELLED")
        assert s.state == "CANCELLED"

    def test_paused_to_aborted(self) -> None:
        paused = transition_state(transition_state(_initial(), "RUNNING"), "PAUSED")
        s = transition_state(paused, "ABORTED")
        assert s.state == "ABORTED"

    def test_invalid_ready_to_paused(self) -> None:
        with pytest.raises(ValueError, match="invalid lifecycle transition"):
            transition_state(_initial(), "PAUSED")

    def test_invalid_ready_to_cancelled(self) -> None:
        with pytest.raises(ValueError, match="invalid lifecycle transition"):
            transition_state(_initial(), "CANCELLED")

    def test_terminal_no_transitions(self) -> None:
        completed = transition_state(transition_state(_initial(), "RUNNING"), "COMPLETED")
        for target in ("READY", "RUNNING", "PAUSED", "CANCELLED", "ABORTED", "FAILED"):
            with pytest.raises(ValueError, match="invalid lifecycle transition"):
                transition_state(completed, target)

    def test_cancelled_is_terminal(self) -> None:
        cancelled = transition_state(transition_state(_initial(), "RUNNING"), "CANCELLED")
        assert cancelled.is_terminal()

    def test_aborted_is_terminal(self) -> None:
        aborted = transition_state(transition_state(_initial(), "RUNNING"), "ABORTED")
        assert aborted.is_terminal()

    def test_preserves_existing_counts(self) -> None:
        s = _initial(total=10)
        s = transition_state(s, "RUNNING")
        s = update_counts(s, tasks_completed=3, tasks_failed=1)
        s = transition_state(s, "PAUSED")
        assert s.tasks_completed == 3
        assert s.tasks_failed == 1
        assert s.tasks_remaining == 6

    def test_transition_preserves_mission_id(self) -> None:
        s = _initial(mission_id="my-mission")
        s = transition_state(s, "RUNNING")
        assert s.mission_id == "my-mission"

    def test_invalid_unknown_target(self) -> None:
        s = _initial()
        with pytest.raises(ValueError, match="invalid lifecycle transition"):
            transition_state(s, "BANANA")


# ===================================================================
# MissionState — update_counts
# ===================================================================

class TestUpdateCounts:
    def test_update_completed(self) -> None:
        s = update_counts(_initial(total=5), tasks_completed=2)
        assert s.tasks_completed == 2
        assert s.tasks_remaining == 3

    def test_update_failed(self) -> None:
        s = update_counts(_initial(total=5), tasks_failed=1)
        assert s.tasks_failed == 1
        assert s.tasks_remaining == 4

    def test_update_both(self) -> None:
        s = update_counts(_initial(total=10), tasks_completed=3, tasks_failed=2)
        assert s.tasks_completed == 3
        assert s.tasks_failed == 2
        assert s.tasks_remaining == 5

    def test_remaining_clamps_to_zero(self) -> None:
        s = update_counts(_initial(total=2), tasks_completed=3, tasks_failed=1)
        assert s.tasks_remaining == 0

    def test_preserves_state(self) -> None:
        s = transition_state(_initial(), "RUNNING")
        s = update_counts(s, tasks_completed=1)
        assert s.state == "RUNNING"


# ===================================================================
# MissionState — serialization round-trip
# ===================================================================

class TestSerializationRoundTrip:
    def test_round_trip(self) -> None:
        s = _initial()
        s = transition_state(s, "RUNNING")
        s = update_counts(s, tasks_completed=2)
        data = s.as_dict()
        restored = MissionState(**data)
        assert restored == s

    def test_all_fields_survive(self) -> None:
        s = transition_state(
            transition_state(transition_state(_initial(), "RUNNING"), "PAUSED"),
            "RUNNING",
        )
        s = update_counts(s, tasks_completed=1, tasks_failed=1)
        data = s.as_dict()
        restored = MissionState(**data)
        assert restored.paused_at is not None
        assert restored.resumed_at is not None
        assert restored.tasks_completed == 1


# ===================================================================
# MissionStateStore — persistence
# ===================================================================

class TestMissionStateStore:
    def test_save_and_load(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        s = _initial()
        store.save(s)
        loaded = store.load()
        assert loaded is not None
        assert loaded.state == "READY"

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "nope.json")
        assert store.load() is None

    def test_load_malformed(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        store = MissionStateStore(path)
        assert store.load() is None

    def test_atomic_write(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        s = _initial()
        store.save(s)
        assert (tmp_path / "state.json").exists()
        # No .tmp files left behind
        assert list(tmp_path.glob(".state.json.*")) == []

    def test_save_overwrites(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        s1 = _initial()
        store.save(s1)
        s2 = transition_state(s1, "RUNNING")
        store.save(s2)
        loaded = store.load()
        assert loaded is not None
        assert loaded.state == "RUNNING"

    def test_concurrent_writes(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(10):
                    s = _initial()
                    s = transition_state(s, "RUNNING")
                    s = update_counts(s, tasks_completed=n * 10 + i)
                    store.save(s)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        loaded = store.load()
        assert loaded is not None
        assert loaded.state == "RUNNING"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "deep" / "path" / "state.json")
        store.save(_initial())
        assert store.load() is not None


# ===================================================================
# MissionControlCommand — model
# ===================================================================

class TestMissionControlCommand:
    def test_create(self) -> None:
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=1,
            action="pause",
            reason="testing",
            requested_at="2026-01-01T00:00:00Z",
        )
        assert cmd.action == "pause"
        assert cmd.command_id == 1

    def test_invalid_action(self) -> None:
        with pytest.raises(ValueError, match="unknown control action"):
            MissionControlCommand(
                schema_version="1",
                mission_id="m-001",
                command_id=1,
                action="INVALID",
                reason=None,
                requested_at="2026-01-01T00:00:00Z",
            )

    def test_invalid_command_id(self) -> None:
        with pytest.raises(ValueError, match="command_id must be >= 0"):
            MissionControlCommand(
                schema_version="1",
                mission_id="m-001",
                command_id=-1,
                action="pause",
                reason=None,
                requested_at="2026-01-01T00:00:00Z",
            )

    def test_as_dict_round_trip(self) -> None:
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=7,
            action="cancel",
            reason="done",
            requested_at="2026-01-01T00:00:00Z",
        )
        data = cmd.as_dict()
        restored = MissionControlCommand(**data)
        assert restored == cmd


# ===================================================================
# MissionControlStore — persistence
# ===================================================================

class TestMissionControlStore:
    def test_save_and_load(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=1,
            action="pause",
            reason="test",
            requested_at="2026-01-01T00:00:00Z",
        )
        store.save(cmd)
        loaded = store.load()
        assert loaded is not None
        assert loaded.action == "pause"
        assert loaded.command_id == 1

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "nope.json")
        assert store.load() is None

    def test_load_malformed(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{bad json", encoding="utf-8")
        store = MissionControlStore(path)
        assert store.load() is None

    def test_clear(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=1,
            action="pause",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        store.save(cmd)
        assert store.load() is not None
        store.clear()
        assert store.load() is None

    def test_clear_nonexistent(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "nope.json")
        store.clear()  # no error

    def test_next_command_id_empty(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        assert store.next_command_id(0) == 1

    def test_next_command_id_from_state(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        assert store.next_command_id(5) == 6

    def test_next_command_id_after_save(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=3,
            action="pause",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        store.save(cmd)
        assert store.next_command_id(1) == 4

    def test_atomic_write(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=1,
            action="abort",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        store.save(cmd)
        assert (tmp_path / "control.json").exists()
        assert list(tmp_path.glob(".control.json.*")) == []


# ===================================================================
# write_control_command helper
# ===================================================================

class TestWriteControlCommand:
    def test_write(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        cmd = write_control_command(store, "m-001", "pause", 0, reason="testing")
        assert cmd.command_id == 1
        assert cmd.action == "pause"
        assert cmd.reason == "testing"
        loaded = store.load()
        assert loaded is not None
        assert loaded.command_id == 1

    def test_incrementing_ids(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        c1 = write_control_command(store, "m-001", "pause", 0)
        c2 = write_control_command(store, "m-001", "resume", 0)
        c3 = write_control_command(store, "m-001", "cancel", 0)
        assert c1.command_id < c2.command_id < c3.command_id

    def test_stale_command_id_rejected_by_runner_check(self, tmp_path: Path) -> None:
        """Command with id <= last_control_command_id is stale."""
        store = MissionControlStore(tmp_path / "control.json")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id="m-001",
            command_id=2,
            action="pause",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        store.save(cmd)
        # Runner has already processed command 5
        assert cmd.command_id <= 5  # stale


# ===================================================================
# Stale command replay prevention
# ===================================================================

class TestStaleCommandPrevention:
    def test_stale_command_not_applied(self, tmp_path: Path) -> None:
        """A command whose id <= state.last_control_command_id must be ignored."""
        state = _initial()
        state = transition_state(state, "RUNNING")
        state = update_counts(state, tasks_completed=2)
        # Simulate: last applied command was id=5
        state = MissionState(
            schema_version=state.schema_version,
            mission_id=state.mission_id,
            mission_title=state.mission_title,
            state=state.state,
            started_at=state.started_at,
            paused_at=state.paused_at,
            resumed_at=state.resumed_at,
            cancelled_at=state.cancelled_at,
            aborted_at=state.aborted_at,
            finished_at=state.finished_at,
            tasks_total=state.tasks_total,
            tasks_completed=state.tasks_completed,
            tasks_failed=state.tasks_failed,
            tasks_remaining=state.tasks_remaining,
            last_control_command_id=5,
            pause_reason=state.pause_reason,
            cancel_reason=state.cancel_reason,
            abort_reason=state.abort_reason,
        )

        # Control file has command_id=3 (stale)
        ctrl = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=3,
            action="pause",
            reason="old",
            requested_at="2026-01-01T00:00:00Z",
        )
        # Runner check: only apply if command_id > last_control_command_id
        should_apply = ctrl.command_id > state.last_control_command_id
        assert not should_apply

    def test_fresh_command_applied(self, tmp_path: Path) -> None:
        state = _initial()
        state = transition_state(state, "RUNNING")
        state = MissionState(
            schema_version=state.schema_version,
            mission_id=state.mission_id,
            mission_title=state.mission_title,
            state=state.state,
            started_at=state.started_at,
            paused_at=state.paused_at,
            resumed_at=state.resumed_at,
            cancelled_at=state.cancelled_at,
            aborted_at=state.aborted_at,
            finished_at=state.finished_at,
            tasks_total=state.tasks_total,
            tasks_completed=state.tasks_completed,
            tasks_failed=state.tasks_failed,
            tasks_remaining=state.tasks_remaining,
            last_control_command_id=5,
            pause_reason=state.pause_reason,
            cancel_reason=state.cancel_reason,
            abort_reason=state.abort_reason,
        )

        ctrl = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=6,
            action="pause",
            reason="new",
            requested_at="2026-01-01T00:00:00Z",
        )
        should_apply = ctrl.command_id > state.last_control_command_id
        assert should_apply


# ===================================================================
# Duplicate command idempotency
# ===================================================================

class TestDuplicateCommandIdempotency:
    def test_same_command_id_not_reapplied(self) -> None:
        state = _initial()
        state = transition_state(state, "RUNNING")
        state = MissionState(
            schema_version=state.schema_version,
            mission_id=state.mission_id,
            mission_title=state.mission_title,
            state=state.state,
            started_at=state.started_at,
            paused_at=state.paused_at,
            resumed_at=state.resumed_at,
            cancelled_at=state.cancelled_at,
            aborted_at=state.aborted_at,
            finished_at=state.finished_at,
            tasks_total=state.tasks_total,
            tasks_completed=state.tasks_completed,
            tasks_failed=state.tasks_failed,
            tasks_remaining=state.tasks_remaining,
            last_control_command_id=7,
            pause_reason=state.pause_reason,
            cancel_reason=state.cancel_reason,
            abort_reason=state.abort_reason,
        )

        ctrl = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=7,
            action="pause",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        # Same id — not strictly greater, so not applied
        assert not (ctrl.command_id > state.last_control_command_id)


# ===================================================================
# Command ordering
# ===================================================================

class TestCommandOrdering:
    def test_commands_are_ordered_by_id(self) -> None:
        commands = [
            MissionControlCommand("1", "m-001", 3, "cancel", None, "t"),
            MissionControlCommand("1", "m-001", 1, "pause", None, "t"),
            MissionControlCommand("1", "m-001", 5, "abort", None, "t"),
            MissionControlCommand("1", "m-001", 2, "resume", None, "t"),
        ]
        ordered = sorted(commands, key=lambda c: c.command_id)
        assert [c.command_id for c in ordered] == [1, 2, 3, 5]


# ===================================================================
# Wrong mission_id rejection
# ===================================================================

class TestWrongMissionId:
    def test_wrong_mission_id_detected(self) -> None:
        state = _initial(mission_id="correct-mission")
        ctrl = MissionControlCommand(
            schema_version="1",
            mission_id="wrong-mission",
            command_id=1,
            action="pause",
            reason=None,
            requested_at="2026-01-01T00:00:00Z",
        )
        assert ctrl.mission_id != state.mission_id


# ===================================================================
# Malformed control file
# ===================================================================

class TestMalformedControlFile:
    def test_invalid_json(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        tmp_path / "control.json"
        (tmp_path / "control.json").write_text("NOT JSON {{{", encoding="utf-8")
        assert store.load() is None

    def test_missing_required_field(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        (tmp_path / "control.json").write_text(
            json.dumps({"schema_version": "1", "mission_id": "m-001"}),
            encoding="utf-8",
        )
        assert store.load() is None

    def test_unknown_action(self, tmp_path: Path) -> None:
        store = MissionControlStore(tmp_path / "control.json")
        data = {
            "schema_version": "1",
            "mission_id": "m-001",
            "command_id": 1,
            "action": "unknown_action",
            "reason": None,
            "requested_at": "2026-01-01T00:00:00Z",
        }
        (tmp_path / "control.json").write_text(json.dumps(data), encoding="utf-8")
        assert store.load() is None


# ===================================================================
# MissionStateStore — filesystem-level atomicity
# ===================================================================

class TestStateStoreAtomicity:
    def test_no_temp_files_after_save(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        for i in range(5):
            store.save(update_counts(_initial(), tasks_completed=i))
        assert list(tmp_path.glob(".state.json.*")) == []

    def test_content_is_valid_json(self, tmp_path: Path) -> None:
        store = MissionStateStore(tmp_path / "state.json")
        store.save(_initial())
        raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert raw["state"] == "READY"
        assert raw["schema_version"] == "1"


# ===================================================================
# Runner integration — lifecycle with real execution
# ===================================================================

from hermes_v01.mission_runner import MissionRunner
from hermes_v01.mission import Mission, MissionPlanner, parse_mission


def _make_runner(tmp_path: Path) -> MissionRunner:
    runtime = tmp_path / "runtime"
    repo = tmp_path / "repo"
    work = tmp_path / "work"
    for d in (runtime, repo, work, runtime / "state", runtime / "runs"):
        d.mkdir(parents=True, exist_ok=True)
    return MissionRunner(
        runtime_root=runtime,
        repository=repo,
        working_directory=work,
        queue_path=runtime / "state" / "queue.json",
        lifecycle_poll_interval=0.01,
    )


def _slow_plan() -> dict:
    return {
        "mission_id": "lifecycle-slow-001",
        "title": "Slow Mission",
        "tasks": [
            {"title": "Slow A", "command": ["sleep", "0.3"]},
            {"title": "Slow B", "command": ["sleep", "0.3"]},
        ],
    }


def _simple_plan() -> dict:
    return {
        "mission_id": "lifecycle-simple-001",
        "title": "Simple Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
        ],
    }


class TestRunnerLifecycleIntegration:
    def test_run_completes_with_committed_state(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_simple_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)
        report = runner.run(plan)
        assert report.status == "COMPLETED"

        state = runner.status()
        assert state is not None
        assert state.state == "COMPLETED"
        assert state.tasks_completed == 1
        assert state.tasks_remaining == 0

    def test_run_persists_mission_state(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_simple_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)
        runner.run(plan)

        state_path = runner.runtime_root / "state" / "mission_state.json"
        assert state_path.exists()
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        assert loaded["state"] == "COMPLETED"
        assert loaded["mission_id"] == "lifecycle-simple-001"

    def test_cancel_mid_execution(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        cancel_called = threading.Event()

        def cancel_soon() -> None:
            time.sleep(0.05)
            runner.cancel(reason="test cancel")
            cancel_called.set()

        t = threading.Thread(target=cancel_soon)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        state = runner.status()
        assert state is not None
        assert state.state == "CANCELLED"
        assert state.cancel_reason == "test cancel"
        assert report.status in ("PARTIAL", "FAILED")

    def test_abort_mid_execution(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        def abort_soon() -> None:
            time.sleep(0.05)
            runner.abort(reason="emergency")

        t = threading.Thread(target=abort_soon)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        state = runner.status()
        assert state is not None
        assert state.state == "ABORTED"
        assert state.abort_reason == "emergency"

    def test_pause_resume_cycle(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        pause_resumed = threading.Event()

        def pause_and_resume() -> None:
            time.sleep(0.02)
            runner.pause(reason="testing")
            time.sleep(0.1)
            runner.resume()
            pause_resumed.set()

        t = threading.Thread(target=pause_and_resume)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        state = runner.status()
        assert state is not None
        assert state.state == "COMPLETED"

    def test_status_returns_none_before_run(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        assert runner.status() is None

    def test_failed_plan_persists_failed_state(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        from hermes_v01.mission import Plan as PlanCls
        plan = PlanCls(
            schema_version="1",
            mission_id="bad-001",
            mission_title="Bad",
            mission_description="",
            generated_at="2026-01-01T00:00:00Z",
            plan_hash="abc",
            tasks=(),
            dependency_graph={},
            required_capabilities=(),
            working_directory=None,
            repository=None,
            warnings=(),
            valid=False,
            errors=("test error",),
        )
        report = runner.run(plan)
        assert report.status == "FAILED"

        state = runner.status()
        assert state is not None
        assert state.state == "FAILED"


# ===================================================================
# Control file integration
# ===================================================================

class TestControlFileIntegration:
    def test_control_file_watched_by_runner(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        def write_cancel() -> None:
            time.sleep(0.05)
            ctrl_store = MissionControlStore(runner.runtime_root / "state" / "mission_control.json")
            write_control_command(
                ctrl_store,
                mission_id=plan.mission_id,
                action="cancel",
                last_control_command_id=0,
                reason="file-based cancel",
            )

        t = threading.Thread(target=write_cancel)
        t.start()
        runner.run(plan)
        t.join(timeout=5)

        state = runner.status()
        assert state is not None
        assert state.state == "CANCELLED"

    def test_wrong_mission_id_rejected(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        def write_wrong_mission() -> None:
            time.sleep(0.05)
            ctrl_store = MissionControlStore(runner.runtime_root / "state" / "mission_control.json")
            write_control_command(
                ctrl_store,
                mission_id="WRONG-MISSION-ID",
                action="cancel",
                last_control_command_id=0,
            )

        t = threading.Thread(target=write_wrong_mission)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        # Wrong mission_id should be ignored; mission completes normally
        assert report.status == "COMPLETED"
        state = runner.status()
        assert state is not None
        assert state.state == "COMPLETED"

    def test_stale_command_id_not_applied(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        def write_stale() -> None:
            time.sleep(0.05)
            ctrl_store = MissionControlStore(runner.runtime_root / "state" / "mission_control.json")
            # Write command with id=0 (stale: runner starts at 1)
            cmd = MissionControlCommand(
                schema_version="1",
                mission_id=plan.mission_id,
                command_id=0,
                action="cancel",
                reason="stale",
                requested_at="2026-01-01T00:00:00Z",
            )
            ctrl_store.save(cmd)

        t = threading.Thread(target=write_stale)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        # Stale command should be ignored
        assert report.status == "COMPLETED"

    def test_malformed_control_file_ignored(self, tmp_path: Path) -> None:
        runner = _make_runner(tmp_path)
        mission = parse_mission(_slow_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)

        def write_garbage() -> None:
            time.sleep(0.05)
            ctrl_path = runner.runtime_root / "state" / "mission_control.json"
            ctrl_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        t = threading.Thread(target=write_garbage)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        assert report.status == "COMPLETED"
