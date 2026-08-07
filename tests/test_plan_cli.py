"""Tests for the hermes-plan CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_v01.plan_cli import (
    cmd_build,
    cmd_enqueue,
    cmd_show,
    cmd_validate,
)
from hermes_v01.work_queue import WorkQueueManager, WorkQueueStateStore


def _write_mission(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _minimal_mission() -> dict:
    return {
        "mission_id": "cli-test-001",
        "title": "CLI Test Mission",
        "description": "Testing CLI commands",
        "tasks": [
            {"title": "Task 1", "command": ["echo", "hello"]},
        ],
    }


def _multi_task_mission() -> dict:
    return {
        "mission_id": "cli-multi-001",
        "title": "Multi-Task CLI",
        "description": "Multiple tasks",
        "tasks": [
            {"title": "Setup", "command": ["mkdir", "-p", "/tmp/build"]},
            {"title": "Build", "command": ["make"], "dependencies": ["cli-multi-001-task-0000"]},
            {"title": "Test", "command": ["make", "test"], "dependencies": ["cli-multi-001-task-0001"]},
        ],
    }


class _Args:
    """Simple args holder for CLI command testing."""
    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestValidateCLI:
    def test_valid_mission(self, tmp_path: Path) -> None:
        path = _write_mission(tmp_path, _minimal_mission())
        args = _Args(mission_file=str(path))
        result = cmd_validate(args)
        assert result == 0

    def test_invalid_mission(self, tmp_path: Path) -> None:
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent"]
        path = _write_mission(tmp_path, data)
        args = _Args(mission_file=str(path))
        result = cmd_validate(args)
        assert result == 1

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{bad", encoding="utf-8")
        args = _Args(mission_file=str(path))
        result = cmd_validate(args)
        assert result == 1

    def test_output_validates(self, tmp_path: Path, capsys) -> None:
        path = _write_mission(tmp_path, _minimal_mission())
        args = _Args(mission_file=str(path))
        cmd_validate(args)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["valid"] is True
        assert output["mission_id"] == "cli-test-001"


class TestBuildCLI:
    def test_build_stdout(self, tmp_path: Path, capsys) -> None:
        path = _write_mission(tmp_path, _minimal_mission())
        args = _Args(mission_file=str(path), output=None)
        result = cmd_build(args)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["schema_version"] == "1"
        assert output["mission_id"] == "cli-test-001"

    def test_build_to_file(self, tmp_path: Path, capsys) -> None:
        path = _write_mission(tmp_path, _minimal_mission())
        out_path = tmp_path / "plan.json"
        args = _Args(mission_file=str(path), output=str(out_path))
        result = cmd_build(args)
        assert result == 0
        assert out_path.exists()
        plan = json.loads(out_path.read_text())
        assert plan["mission_id"] == "cli-test-001"

    def test_build_invalid_mission(self, tmp_path: Path, capsys) -> None:
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent"]
        path = _write_mission(tmp_path, data)
        args = _Args(mission_file=str(path), output=None)
        result = cmd_build(args)
        assert result == 1

    def test_build_multi_task(self, tmp_path: Path, capsys) -> None:
        path = _write_mission(tmp_path, _multi_task_mission())
        args = _Args(mission_file=str(path), output=None)
        result = cmd_build(args)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output["tasks"]) == 3


class TestShowCLI:
    def test_show_plan(self, tmp_path: Path, capsys) -> None:
        from hermes_v01.mission import MissionPlanner, parse_mission, save_plan

        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        args = _Args(plan_file=str(plan_path))
        result = cmd_show(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["mission_id"] == "cli-test-001"

    def test_show_nonexistent_file(self, tmp_path: Path) -> None:
        args = _Args(plan_file=str(tmp_path / "nope.json"))
        result = cmd_show(args)
        assert result == 1


class TestEnqueueCLI:
    def test_enqueue_plan(self, tmp_path: Path, capsys) -> None:
        from hermes_v01.mission import MissionPlanner, parse_mission, save_plan

        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        queue_path = tmp_path / "queue.json"
        args = _Args(plan_file=str(plan_path), queue_file=str(queue_path))
        result = cmd_enqueue(args)
        assert result == 0

        # Verify queue was populated
        store = WorkQueueStateStore(queue_path)
        mgr = WorkQueueManager(state_store=store)
        assert len(mgr.items()) == 1

    def test_enqueue_duplicate_rejected(self, tmp_path: Path) -> None:
        from hermes_v01.mission import MissionPlanner, parse_mission, save_plan

        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        queue_path = tmp_path / "queue.json"
        args = _Args(plan_file=str(plan_path), queue_file=str(queue_path))

        cmd_enqueue(args)  # first enqueue
        result = cmd_enqueue(args)  # duplicate
        assert result == 1

    def test_enqueue_invalid_plan(self, tmp_path: Path) -> None:
        from hermes_v01.mission import MissionPlanner, parse_mission, save_plan

        planner = MissionPlanner()
        data = _minimal_mission()
        data["tasks"][0]["dependencies"] = ["nonexistent"]
        mission = parse_mission(data)
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        queue_path = tmp_path / "queue.json"
        args = _Args(plan_file=str(plan_path), queue_file=str(queue_path))
        result = cmd_enqueue(args)
        assert result == 1

    def test_enqueue_output(self, tmp_path: Path, capsys) -> None:
        from hermes_v01.mission import MissionPlanner, parse_mission, save_plan

        planner = MissionPlanner()
        mission = parse_mission(_minimal_mission())
        plan = planner.build(mission)

        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        queue_path = tmp_path / "queue.json"
        args = _Args(plan_file=str(plan_path), queue_file=str(queue_path))
        cmd_enqueue(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["count"] == 1
        assert len(output["enqueued"]) == 1
