"""Comprehensive tests for the Mission Planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evosia.mission import (
    Mission,
    MissionPlanner,
    MissionTask,
    Plan,
    PlanTask,
    RetryPolicy,
    enqueue_plan,
    load_mission,
    load_plan,
    parse_mission,
    save_plan,
)
from evosia.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore
from evosia.capabilities import CapabilityManager, CapabilityMetadata, CapabilityRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_mission() -> dict:
    return {
        "mission_id": "test-mission-001",
        "title": "Test Mission",
        "description": "A minimal test mission",
        "tasks": [
            {"title": "Task 1", "command": ["echo", "hello"]},
        ],
    }


def _multi_task_mission() -> dict:
    return {
        "mission_id": "multi-task-001",
        "title": "Multi-Task Mission",
        "description": "Mission with dependencies",
        "tasks": [
            {"title": "Setup", "command": ["mkdir", "-p", "/tmp/build"]},
            {"title": "Build", "command": ["make", "build"], "dependencies": ["multi-task-001-task-0000"]},
            {"title": "Test", "command": ["make", "test"], "dependencies": ["multi-task-001-task-0001"]},
        ],
    }


def _write_mission(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_defaults(self) -> None:
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.retry_delay_seconds == 1.0
        assert p.max_retry_delay_seconds == 60.0
        assert p.retry_backoff_multiplier == 2.0
        assert p.retryable is True

    def test_custom(self) -> None:
        p = RetryPolicy(max_retries=5, retry_delay_seconds=2.0, retryable=False)
        assert p.max_retries == 5
        assert p.retryable is False

    def test_invalid_max_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            RetryPolicy(max_retries=-1)

    def test_invalid_delay(self) -> None:
        with pytest.raises(ValueError, match="retry_delay_seconds"):
            RetryPolicy(retry_delay_seconds=0)

    def test_invalid_backoff(self) -> None:
        with pytest.raises(ValueError, match="retry_backoff_multiplier"):
            RetryPolicy(retry_backoff_multiplier=1.0)

    def test_as_dict(self) -> None:
        d = RetryPolicy().as_dict()
        assert d["max_retries"] == 3
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# MissionTask
# ---------------------------------------------------------------------------

class TestMissionTask:
    def test_minimal(self) -> None:
        t = MissionTask(title="T", command=["echo"])
        assert t.title == "T"
        assert t.task_id is None
        assert t.priority == 100

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError, match="title"):
            MissionTask(title="", command=["echo"])

    def test_empty_command_rejected(self) -> None:
        with pytest.raises(ValueError, match="command"):
            MissionTask(title="T", command=[])

    def test_empty_task_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="task_id"):
            MissionTask(title="T", command=["echo"], task_id="")

    def test_as_dict(self) -> None:
        t = MissionTask(title="T", command=["echo"], task_id="t1", priority=50)
        d = t.as_dict()
        assert d["task_id"] == "t1"
        assert d["priority"] == 50


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

class TestMission:
    def test_minimal(self) -> None:
        m = Mission(mission_id="m1", title="M", description="", tasks=(
            MissionTask(title="T", command=["echo"]),
       ))
        assert m.mission_id == "m1"
        assert len(m.tasks) == 1

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="mission_id"):
            Mission(mission_id="", title="M", description="", tasks=(
                MissionTask(title="T", command=["echo"]),
            ))

    def test_empty_tasks_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one task"):
            Mission(mission_id="m1", title="M", description="", tasks=())

    def test_as_dict(self) -> None:
        m = Mission(mission_id="m1", title="M", description="D", tasks=(
            MissionTask(title="T", command=["echo"]),
       ))
        d = m.as_dict()
        assert d["mission_id"] == "m1"
        assert d["schema_version"] == "1"


# ---------------------------------------------------------------------------
# Mission loading
# ---------------------------------------------------------------------------

class TestMissionLoading:
    def test_load_minimal(self, tmp_path: Path) -> None:
        path = _write_mission(tmp_path, _minimal_mission())
        mission = load_mission(path)
        assert mission.mission_id == "test-mission-001"
        assert len(mission.tasks) == 1

    def test_load_multi_task(self, tmp_path: Path) -> None:
        path = _write_mission(tmp_path, _multi_task_mission())
        mission = load_mission(path)
        assert len(mission.tasks) == 3

    def test_parse_mission_minimal(self) -> None:
        mission = parse_mission(_minimal_mission())
        assert mission.mission_id == "test-mission-001"

    def test_parse_mission_with_retry_policy(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["retry_policy"] = {"max_retries": 5, "retryable": False}
        mission = parse_mission(data)
        assert mission.tasks[0].retry_policy is not None
        assert mission.tasks[0].retry_policy.max_retries == 5

    def test_parse_mission_with_default_retry(self) -> None:
        data = _minimal_mission()
        data["default_retry_policy"] = {"max_retries": 10}
        mission = parse_mission(data)
        assert mission.default_retry_policy.max_retries == 10

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{invalid", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_mission(path)

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        path = _write_mission(tmp_path, {"description": "no id or title"})
        with pytest.raises(KeyError):
            load_mission(path)

    def test_load_preserves_all_fields(self, tmp_path: Path) -> None:
        data = {
            "mission_id": "full-001",
            "title": "Full Mission",
            "description": "Complete",
            "goals": ["goal1", "goal2"],
            "constraints": ["constraint1"],
            "required_capabilities": ["local"],
            "working_directory": "/tmp/work",
            "repository": "/tmp/repo",
            "metadata": {"author": "test"},
            "tasks": [
                {
                    "task_id": "explicit-id",
                    "title": "Task",
                    "command": ["echo"],
                    "priority": 50,
                    "required_capabilities": ["local"],
                    "metadata": {"key": "val"},
                },
            ],
        }
        path = _write_mission(tmp_path, data)
        mission = load_mission(path)
        assert mission.goals == ("goal1", "goal2")
        assert mission.constraints == ("constraint1",)
        assert mission.required_capabilities == ("local",)
        assert mission.working_directory == "/tmp/work"
        assert mission.repository == "/tmp/repo"
        assert mission.metadata == {"author": "test"}
        assert mission.tasks[0].task_id == "explicit-id"
        assert mission.tasks[0].priority == 50


# ---------------------------------------------------------------------------
# Planner — validation
# ---------------------------------------------------------------------------

class TestPlannerValidation:
    def test_valid_minimal(self) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        errors, warnings = planner.validate(mission)
        assert errors == []

    def test_valid_multi_task(self) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_multi_task_mission())
        errors, warnings = planner.validate(mission)
        assert errors == []

    def test_duplicate_task_ids_rejected(self) -> None:
        data = _minimal_mission()
        data["tasks"] = [
            {"task_id": "same", "title": "A", "command": ["echo"]},
            {"task_id": "same", "title": "B", "command": ["echo"]},
        ]
        planner = MissionPlanner()
        mission = parse_mission(data)
        errors, _ = planner.validate(mission)
        assert any("Duplicate" in e for e in errors)

    def test_unknown_dependency_rejected(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent-task"]
        planner = MissionPlanner()
        mission = parse_mission(data)
        errors, _ = planner.validate(mission)
        assert any("unknown task" in e.lower() for e in errors)

    def test_cycle_detection(self) -> None:
        data = {
            "mission_id": "cycle-001",
            "title": "Cycle",
            "description": "",
            "tasks": [
                {"task_id": "a", "title": "A", "command": ["echo"], "dependencies": ["b"]},
                {"task_id": "b", "title": "B", "command": ["echo"], "dependencies": ["a"]},
            ],
        }
        planner = MissionPlanner()
        mission = parse_mission(data)
        errors, _ = planner.validate(mission)
        assert any("cycle" in e.lower() for e in errors)

    def test_negative_priority_rejected(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["priority"] = -10
        planner = MissionPlanner()
        mission = parse_mission(data)
        errors, _ = planner.validate(mission)
        assert any("negative priority" in e.lower() for e in errors)

    def test_invalid_retry_policy_rejected(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["retry_policy"] = {"max_retries": -1}
        planner = MissionPlanner()
        with pytest.raises(ValueError, match="max_retries"):
            parse_mission(data)


# ---------------------------------------------------------------------------
# Planner — build
# ---------------------------------------------------------------------------

class TestPlannerBuild:
    def test_build_minimal(self) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)
        assert plan.valid is True
        assert len(plan.tasks) == 1
        assert plan.tasks[0].task_id == "test-mission-001-task-0000"

    def test_build_multi_task(self) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_multi_task_mission())
        plan = planner.build(mission)
        assert plan.valid is True
        assert len(plan.tasks) == 3

    def test_explicit_task_ids_preserved(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["task_id"] = "my-custom-id"
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].task_id == "my-custom-id"

    def test_generated_task_ids_deterministic(self) -> None:
        planner = MissionPlanner()
        m1 = parse_mission(_minimal_mission())
        m2 = parse_mission(_minimal_mission())
        p1 = planner.build(m1)
        p2 = planner.build(m2)
        assert p1.tasks[0].task_id == p2.tasks[0].task_id

    def test_dependency_graph_built(self) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_multi_task_mission())
        plan = planner.build(mission)
        # Third task depends on second (which depends on first)
        assert "multi-task-001-task-0001" in plan.dependency_graph["multi-task-001-task-0002"]

    def test_priority_normalized(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["priority"] = 10
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].priority == 10

    def test_retry_policy_applied(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["retry_policy"] = {"max_retries": 7, "retryable": False}
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].retry_policy.max_retries == 7
        assert plan.tasks[0].retry_policy.retryable is False

    def test_default_retry_policy_used(self) -> None:
        data = _minimal_mission()
        data["default_retry_policy"] = {"max_retries": 99}
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].retry_policy.max_retries == 99

    def test_required_capabilities_aggregated(self) -> None:
        data = _minimal_mission()
        data["required_capabilities"] = ["cap-a"]
        data["tasks"][0]["required_capabilities"] = ["cap-b"]
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert "cap-a" in plan.required_capabilities
        assert "cap-b" in plan.required_capabilities

    def test_invalid_plan_not_valid(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent"]
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.valid is False
        assert len(plan.errors) > 0

    def test_plan_hash_deterministic(self) -> None:
        planner = MissionPlanner()
        m1 = parse_mission(_minimal_mission())
        m2 = parse_mission(_minimal_mission())
        p1 = planner.build(m1)
        p2 = planner.build(m2)
        assert p1.plan_hash == p2.plan_hash

    def test_working_directory_inherited(self) -> None:
        data = _minimal_mission()
        data["working_directory"] = "/tmp/work"
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].working_directory == "/tmp/work"

    def test_task_working_directory_overrides(self) -> None:
        data = _minimal_mission()
        data["working_directory"] = "/tmp/work"
        data["tasks"][0]["working_directory"] = "/tmp/special"
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].working_directory == "/tmp/special"

    def test_metadata_preserved(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["metadata"] = {"custom": "value"}
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.tasks[0].metadata == {"custom": "value"}


# ---------------------------------------------------------------------------
# Planner — capability validation
# ---------------------------------------------------------------------------

class TestCapabilityValidation:
    def test_missing_capability_rejected(self, tmp_path: Path) -> None:
        registry = CapabilityRegistry(tmp_path / "cap.json")
        CapabilityManager(registry, [])  # registers "local"

        planner = MissionPlanner()
        data = _minimal_mission()
        data["required_capabilities"] = ["nonexistent"]
        mission = parse_mission(data)
        plan = planner.build(mission, capability_registry=registry)
        assert plan.valid is False
        assert any("not found" in e.lower() for e in plan.errors)

    def test_disabled_capability_rejected(self, tmp_path: Path) -> None:
        registry = CapabilityRegistry(tmp_path / "cap.json")
        CapabilityManager(registry, [])
        registry.disable("local")

        planner = MissionPlanner()
        data = _minimal_mission()
        data["required_capabilities"] = ["local"]
        mission = parse_mission(data)
        plan = planner.build(mission, capability_registry=registry)
        assert plan.valid is False
        assert any("disabled" in e.lower() for e in plan.errors)

    def test_available_capability_passes(self, tmp_path: Path) -> None:
        registry = CapabilityRegistry(tmp_path / "cap.json")
        CapabilityManager(registry, [])

        planner = MissionPlanner()
        data = _minimal_mission()
        data["required_capabilities"] = ["local"]
        mission = parse_mission(data)
        plan = planner.build(mission, capability_registry=registry)
        assert plan.valid is True

    def test_no_registry_skips_check(self) -> None:
        planner = MissionPlanner()
        data = _minimal_mission()
        data["required_capabilities"] = ["nonexistent"]
        mission = parse_mission(data)
        plan = planner.build(mission, capability_registry=None)
        # No registry = no capability check
        assert plan.valid is True


# ---------------------------------------------------------------------------
# Plan serialization
# ---------------------------------------------------------------------------

class TestPlanSerialization:
    def test_save_and_load(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)
        loaded = load_plan(plan_path)

        assert loaded.mission_id == plan.mission_id
        assert len(loaded.tasks) == len(plan.tasks)
        assert loaded.plan_hash == plan.plan_hash

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "deep" / "nested" / "plan.json"
        save_plan(plan, plan_path)
        assert plan_path.exists()

    def test_load_preserves_all_fields(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        data = _minimal_mission()
        data["tasks"][0]["metadata"] = {"key": "val"}
        mission = parse_mission(data)
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)
        loaded = load_plan(plan_path)

        assert loaded.working_directory == plan.working_directory
        assert loaded.repository == plan.repository
        assert loaded.warnings == plan.warnings
        assert loaded.valid == plan.valid
        assert loaded.errors == plan.errors


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

class TestEnqueue:
    def test_enqueue_creates_work_items(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueued = enqueue_plan(plan, queue_path)
        assert len(enqueued) == 1
        assert enqueued[0] == "test-mission-001-task-0000"

    def test_enqueued_items_in_queue(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        assert len(mgr.items()) == 1
        assert mgr.get("test-mission-001-task-0000") is not None

    def test_enqueue_preserves_dependencies(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_multi_task_mission())
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        assert len(mgr.items()) == 3

    def test_duplicate_enqueue_rejected(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        with pytest.raises(ValueError, match="already exists"):
            enqueue_plan(plan, queue_path)

    def test_enqueue_invalid_plan_rejected(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent"]
        mission = parse_mission(data)
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        with pytest.raises(ValueError, match="invalid plan"):
            enqueue_plan(plan, queue_path)

    def test_enqueued_work_items_have_correct_retry(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        data = _minimal_mission()
        data["tasks"][0]["retry_policy"] = {"max_retries": 7}
        mission = parse_mission(data)
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        item = mgr.get("test-mission-001-task-0000")
        assert item.max_retries == 7

    def test_enqueued_work_items_have_correct_priority(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        data = _minimal_mission()
        data["tasks"][0]["priority"] = 10
        mission = parse_mission(data)
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        item = mgr.get("test-mission-001-task-0000")
        assert item.priority == 10

    def test_enqueued_tasks_start_blocked(self, tmp_path: Path) -> None:
        planner = MissionPlanner()
        mission = parse_mission(_multi_task_mission())
        plan = planner.build(mission)

        queue_path = tmp_path / "queue.json"
        enqueue_plan(plan, queue_path)

        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        # First task has no deps -> READY, others BLOCKED
        first = mgr.get("multi-task-001-task-0000")
        assert first.state == "READY"
        second = mgr.get("multi-task-001-task-0001")
        assert second.state == "BLOCKED"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        planner = MissionPlanner()
        m1 = parse_mission(_multi_task_mission())
        m2 = parse_mission(_multi_task_mission())
        p1 = planner.build(m1)
        p2 = planner.build(m2)
        # Same logical plan
        assert len(p1.tasks) == len(p2.tasks)
        for t1, t2 in zip(p1.tasks, p2.tasks):
            assert t1.task_id == t2.task_id
            assert t1.title == t2.title
            assert t1.command == t2.command
            assert t1.dependencies == t2.dependencies
            assert t1.priority == t2.priority

    def test_deterministic_task_ids(self) -> None:
        planner = MissionPlanner()
        for _ in range(5):
            mission = parse_mission(_minimal_mission())
            plan = planner.build(mission)
            assert plan.tasks[0].task_id == "test-mission-001-task-0000"

    def test_plan_hash_stable(self) -> None:
        planner = MissionPlanner()
        hashes = set()
        for _ in range(5):
            mission = parse_mission(_minimal_mission())
            plan = planner.build(mission)
            hashes.add(plan.plan_hash)
        assert len(hashes) == 1


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_existing_work_item_compatible(self) -> None:
        """Plan tasks produce WorkItems compatible with existing queue."""
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        work_item = plan.tasks[0].to_work_item()
        assert isinstance(work_item, WorkItem)
        assert work_item.task_id == "test-mission-001-task-0000"
        assert work_item.state == "BLOCKED"

    def test_enqueue_into_existing_queue(self, tmp_path: Path) -> None:
        """Enqueue plan tasks into a queue that already has items."""
        # Create existing queue
        store_path = tmp_path / "queue.json"
        store = WorkQueueStateStore(store_path)
        existing = WorkItem(task_id="existing", title="Existing")
        mgr = WorkQueueManager(state_store=store, items=[existing])
        assert len(mgr.items()) == 1

        # Enqueue plan
        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)
        enqueue_plan(plan, store_path)

        # Verify both exist
        mgr2 = WorkQueueManager(state_store=WorkQueueStateStore(store_path))
        assert len(mgr2.items()) == 2
        assert mgr2.get("existing") is not None
        assert mgr2.get("test-mission-001-task-0000") is not None

    def test_plan_task_to_work_item_fields(self) -> None:
        """All WorkItem fields are correctly mapped."""
        plan_task = PlanTask(
            task_id="t1",
            title="Task",
            command=["echo"],
            dependencies=("dep1",),
            priority=50,
            retry_policy=RetryPolicy(max_retries=5, retry_delay_seconds=2.0),
            required_capabilities=("local",),
            working_directory="/tmp",
            metadata={"k": "v"},
        )
        wi = plan_task.to_work_item()
        assert wi.task_id == "t1"
        assert wi.priority == 50
        assert wi.dependencies == ("dep1",)
        assert wi.max_retries == 5
        assert wi.retry_delay_seconds == 2.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_task_no_deps(self) -> None:
        planner = MissionPlanner()
        data = {
            "mission_id": "solo",
            "title": "Solo",
            "description": "",
            "tasks": [{"title": "Only", "command": ["ls"]}],
        }
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.valid is True
        assert plan.tasks[0].dependencies == ()

    def test_many_tasks(self) -> None:
        tasks = [
            {"task_id": f"t{i}", "title": f"Task {i}", "command": ["echo", str(i)]}
            for i in range(50)
        ]
        data = {
            "mission_id": "big",
            "title": "Big",
            "description": "",
            "tasks": tasks,
        }
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.valid is True
        assert len(plan.tasks) == 50

    def test_chain_dependencies(self) -> None:
        tasks = [
            {"task_id": f"t{i}", "title": f"Task {i}", "command": ["echo"],
             "dependencies": [f"t{i-1}"] if i > 0 else []}
            for i in range(5)
        ]
        data = {
            "mission_id": "chain",
            "title": "Chain",
            "description": "",
            "tasks": tasks,
        }
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.valid is True
        # Each task (except first) depends on previous
        for i in range(1, 5):
            assert f"t{i-1}" in plan.dependency_graph[f"t{i}"]

    def test_diamond_dependency(self) -> None:
        """A -> B, A -> C, B -> D, C -> D"""
        data = {
            "mission_id": "diamond",
            "title": "Diamond",
            "description": "",
            "tasks": [
                {"task_id": "a", "title": "A", "command": ["echo"]},
                {"task_id": "b", "title": "B", "command": ["echo"], "dependencies": ["a"]},
                {"task_id": "c", "title": "C", "command": ["echo"], "dependencies": ["a"]},
                {"task_id": "d", "title": "D", "command": ["echo"], "dependencies": ["b", "c"]},
            ],
        }
        planner = MissionPlanner()
        mission = parse_mission(data)
        plan = planner.build(mission)
        assert plan.valid is True

    def test_self_dependency_rejected(self) -> None:
        data = {
            "mission_id": "self",
            "title": "Self",
            "description": "",
            "tasks": [
                {"task_id": "a", "title": "A", "command": ["echo"], "dependencies": ["a"]},
            ],
        }
        planner = MissionPlanner()
        mission = parse_mission(data)
        errors, _ = planner.validate(mission)
        assert len(errors) > 0

    def test_empty_goals_and_constraints(self) -> None:
        data = _minimal_mission()
        data["goals"] = []
        data["constraints"] = []
        mission = parse_mission(data)
        assert mission.goals == ()
        assert mission.constraints == ()
