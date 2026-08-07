"""Comprehensive tests for the Mission Constraint Engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hermes_v01.mission import Mission, MissionPlanner, MissionTask, parse_mission
from hermes_v01.mission_constraints import (
    ConstraintEngine,
    ConstraintResult,
    DependencyPolicyConstraint,
    ExecutionWindowConstraint,
    MissionConstraint,
    RequiredCapabilityConstraint,
    RepositoryConstraint,
    ResourceLimitConstraint,
    RuntimeVersionConstraint,
    WorkingDirectoryConstraint,
    validate_mission_constraints,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_mission() -> dict:
    return {
        "mission_id": "constraint-test-001",
        "title": "Constraint Test Mission",
        "description": "Test mission for constraint validation",
        "tasks": [
            {"title": "Task 1", "command": ["echo", "hello"]},
        ],
    }


def _constrained_mission() -> dict:
    return {
        "mission_id": "constrained-001",
        "title": "Constrained Mission",
        "description": "Mission with constraints",
        "constraints": ["runtime_version", "repository", "working_directory"],
        "repository": "/tmp/test-repo",
        "working_directory": "/tmp/test-work",
        "tasks": [
            {"title": "Task 1", "command": ["echo", "hello"]},
        ],
    }


# ---------------------------------------------------------------------------
# ConstraintResult Tests
# ---------------------------------------------------------------------------

class TestConstraintResult:
    def test_result_fields(self) -> None:
        r = ConstraintResult(
            constraint_type="test",
            name="test_constraint",
            satisfied=True,
            message="all good",
        )
        assert r.constraint_type == "test"
        assert r.name == "test_constraint"
        assert r.satisfied is True
        assert r.message == "all good"
        assert r.details == {}

    def test_result_with_details(self) -> None:
        r = ConstraintResult(
            constraint_type="test",
            name="test_constraint",
            satisfied=False,
            message="failed",
            details={"key": "value"},
        )
        assert r.details == {"key": "value"}

    def test_result_as_dict(self) -> None:
        r = ConstraintResult(
            constraint_type="test",
            name="test_constraint",
            satisfied=True,
            message="ok",
            details={"x": 1},
        )
        d = r.as_dict()
        assert d["constraint_type"] == "test"
        assert d["satisfied"] is True
        assert d["details"] == {"x": 1}

    def test_result_deterministic(self) -> None:
        args = dict(constraint_type="t", name="n", satisfied=True, message="m")
        r1 = ConstraintResult(**args)
        r2 = ConstraintResult(**args)
        assert r1.as_dict() == r2.as_dict()


# ---------------------------------------------------------------------------
# RequiredCapabilityConstraint Tests
# ---------------------------------------------------------------------------

class TestRequiredCapabilityConstraint:
    def test_no_capabilities_required(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RequiredCapabilityConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True
        assert "no capabilities" in r.message

    def test_capabilities_required_no_registry(self) -> None:
        data = _minimal_mission()
        data["required_capabilities"] = ["cap-a", "cap-b"]
        mission = parse_mission(data)
        c = RequiredCapabilityConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is False
        assert "registry not available" in r.message

    def test_capabilities_from_tasks(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["required_capabilities"] = ["task-cap"]
        mission = parse_mission(data)
        c = RequiredCapabilityConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is False

    def test_constraint_type(self) -> None:
        c = RequiredCapabilityConstraint()
        assert c.constraint_type == "required_capabilities"


# ---------------------------------------------------------------------------
# RuntimeVersionConstraint Tests
# ---------------------------------------------------------------------------

class TestRuntimeVersionConstraint:
    def test_current_version_satisfies(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RuntimeVersionConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True
        assert "meets version" in r.message

    def test_minimum_version_check(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RuntimeVersionConstraint()
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        r = c.evaluate(mission, {"min_python_version": current})
        assert r.satisfied is True

    def test_minimum_version_fails(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RuntimeVersionConstraint()
        r = c.evaluate(mission, {"min_python_version": "99.0"})
        assert r.satisfied is False
        assert "below minimum" in r.message

    def test_maximum_version_check(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RuntimeVersionConstraint()
        r = c.evaluate(mission, {"max_python_version": "99.0"})
        assert r.satisfied is True

    def test_maximum_version_fails(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RuntimeVersionConstraint()
        r = c.evaluate(mission, {"max_python_version": "2.0"})
        assert r.satisfied is False
        assert "exceeds maximum" in r.message

    def test_constraint_type(self) -> None:
        c = RuntimeVersionConstraint()
        assert c.constraint_type == "runtime_version"


# ---------------------------------------------------------------------------
# RepositoryConstraint Tests
# ---------------------------------------------------------------------------

class TestRepositoryConstraint:
    def test_no_repository_required(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = RepositoryConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True

    def test_repository_path_exists(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = RepositoryConstraint()
        r = c.evaluate(mission, {"repository": tmp_path})
        assert r.satisfied is True

    def test_repository_path_not_exists(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = RepositoryConstraint()
        r = c.evaluate(mission, {"repository": tmp_path / "nonexistent"})
        assert r.satisfied is False
        assert "does not exist" in r.message

    def test_repository_path_not_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        mission = parse_mission(_minimal_mission())
        c = RepositoryConstraint()
        r = c.evaluate(mission, {"repository": f})
        assert r.satisfied is False
        assert "not a directory" in r.message

    def test_mission_references_repository(self) -> None:
        data = _minimal_mission()
        data["repository"] = "my-repo"
        mission = parse_mission(data)
        c = RepositoryConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is False
        assert "no repository path provided" in r.message

    def test_constraint_type(self) -> None:
        c = RepositoryConstraint()
        assert c.constraint_type == "repository"


# ---------------------------------------------------------------------------
# WorkingDirectoryConstraint Tests
# ---------------------------------------------------------------------------

class TestWorkingDirectoryConstraint:
    def test_no_working_directory(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = WorkingDirectoryConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True

    def test_working_directory_exists(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = WorkingDirectoryConstraint()
        r = c.evaluate(mission, {"working_directory": tmp_path})
        assert r.satisfied is True

    def test_working_directory_not_exists(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = WorkingDirectoryConstraint()
        r = c.evaluate(mission, {"working_directory": tmp_path / "nonexistent"})
        assert r.satisfied is False
        assert "does not exist" in r.message

    def test_constraint_type(self) -> None:
        c = WorkingDirectoryConstraint()
        assert c.constraint_type == "working_directory"


# ---------------------------------------------------------------------------
# ResourceLimitConstraint Tests
# ---------------------------------------------------------------------------

class TestResourceLimitConstraint:
    def test_no_resource_limits(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ResourceLimitConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True

    def test_disk_space_check(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = ResourceLimitConstraint()
        r = c.evaluate(mission, {"min_disk_space_mb": 1, "working_directory": tmp_path})
        assert r.satisfied is True
        assert "disk_free_mb" in r.details

    def test_disk_space_insufficient(self, tmp_path: Path) -> None:
        mission = parse_mission(_minimal_mission())
        c = ResourceLimitConstraint()
        r = c.evaluate(mission, {"min_disk_space_mb": 999999999, "working_directory": tmp_path})
        assert r.satisfied is False
        assert "insufficient disk" in r.message

    def test_constraint_type(self) -> None:
        c = ResourceLimitConstraint()
        assert c.constraint_type == "resource_limits"


# ---------------------------------------------------------------------------
# ExecutionWindowConstraint Tests
# ---------------------------------------------------------------------------

class TestExecutionWindowConstraint:
    def test_no_window(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True

    def test_window_open(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission, {"window_start": "2020-01-01T00:00:00Z"})
        assert r.satisfied is True

    def test_window_not_yet_open(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission, {"window_start": "2099-12-31T23:59:59Z"})
        assert r.satisfied is False
        assert "not opened yet" in r.message

    def test_window_closed(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission, {"window_end": "2020-01-01T00:00:00Z"})
        assert r.satisfied is False
        assert "has closed" in r.message

    def test_excluded_day(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%A")
        r = c.evaluate(mission, {"excluded_days": [today]})
        assert r.satisfied is False
        assert "excluded" in r.message

    def test_invalid_window_start(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission, {"window_start": "not-a-date"})
        assert r.satisfied is False
        assert "invalid" in r.message

    def test_invalid_window_end(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = ExecutionWindowConstraint()
        r = c.evaluate(mission, {"window_end": "not-a-date"})
        assert r.satisfied is False
        assert "invalid" in r.message

    def test_constraint_type(self) -> None:
        c = ExecutionWindowConstraint()
        assert c.constraint_type == "execution_window"


# ---------------------------------------------------------------------------
# DependencyPolicyConstraint Tests
# ---------------------------------------------------------------------------

class TestDependencyPolicyConstraint:
    def test_no_policy(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = DependencyPolicyConstraint()
        r = c.evaluate(mission)
        assert r.satisfied is True

    def test_network_allowed(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["command"] = ["curl", "http://example.com"]
        mission = parse_mission(data)
        c = DependencyPolicyConstraint()
        r = c.evaluate(mission, {"allow_network": True})
        assert r.satisfied is True

    def test_network_disallowed(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["command"] = ["curl", "http://example.com"]
        mission = parse_mission(data)
        c = DependencyPolicyConstraint()
        r = c.evaluate(mission, {"allow_network": False})
        assert r.satisfied is False
        assert "network access" in r.message

    def test_deterministic_check(self) -> None:
        data = _minimal_mission()
        data["tasks"][0]["command"] = ["date"]
        mission = parse_mission(data)
        c = DependencyPolicyConstraint()
        r = c.evaluate(mission, {"require_deterministic": True})
        assert r.satisfied is False
        assert "non-deterministic" in r.message

    def test_deterministic_check_clean(self) -> None:
        mission = parse_mission(_minimal_mission())
        c = DependencyPolicyConstraint()
        r = c.evaluate(mission, {"require_deterministic": True})
        assert r.satisfied is True

    def test_constraint_type(self) -> None:
        c = DependencyPolicyConstraint()
        assert c.constraint_type == "dependency_policy"


# ---------------------------------------------------------------------------
# ConstraintEngine Tests
# ---------------------------------------------------------------------------

class TestConstraintEngine:
    def test_engine_no_constraints(self) -> None:
        mission = parse_mission(_minimal_mission())
        engine = ConstraintEngine()
        results = engine.validate(mission)
        assert len(results) == 0

    def test_engine_add_constraint(self) -> None:
        mission = parse_mission(_minimal_mission())
        engine = ConstraintEngine()
        engine.add_constraint(RuntimeVersionConstraint())
        results = engine.validate(mission)
        assert len(results) == 1
        assert results[0].satisfied is True

    def test_engine_add_by_name(self) -> None:
        mission = parse_mission(_minimal_mission())
        engine = ConstraintEngine()
        engine.add_constraints_by_name(["runtime_version", "repository"])
        results = engine.validate(mission)
        assert len(results) == 2

    def test_engine_unknown_constraint_name(self) -> None:
        mission = parse_mission(_minimal_mission())
        engine = ConstraintEngine()
        engine.add_constraints_by_name(["nonexistent"])
        results = engine.validate(mission)
        assert len(results) == 0

    def test_engine_validate_mission_constraints(self) -> None:
        mission = parse_mission(_constrained_mission())
        engine = ConstraintEngine()
        errors, warnings = engine.validate_mission_constraints(mission)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

    def test_engine_summary(self) -> None:
        mission = parse_mission(_minimal_mission())
        engine = ConstraintEngine()
        engine.add_constraint(RuntimeVersionConstraint())
        results = engine.validate(mission)
        summary = engine.get_results_summary(results)
        assert summary["total"] == 1
        assert summary["satisfied"] == 1
        assert summary["unsatisfied"] == 0

    def test_constraint_map_completeness(self) -> None:
        expected = {
            "required_capabilities", "runtime_version", "repository",
            "working_directory", "resource_limits", "execution_window",
            "dependency_policy",
        }
        assert set(ConstraintEngine.CONSTRAINT_MAP.keys()) == expected


# ---------------------------------------------------------------------------
# validate_mission_constraints Tests
# ---------------------------------------------------------------------------

class TestValidateMissionConstraintsFunction:
    def test_no_constraints(self) -> None:
        mission = parse_mission(_minimal_mission())
        errors, warnings = validate_mission_constraints(mission)
        assert errors == []
        assert warnings == []

    def test_with_constraints(self) -> None:
        mission = parse_mission(_constrained_mission())
        errors, warnings = validate_mission_constraints(mission)
        assert isinstance(errors, list)


# ---------------------------------------------------------------------------
# Planner Integration Tests
# ---------------------------------------------------------------------------

class TestPlannerConstraintIntegration:
    def test_planner_build_with_constraints(self, tmp_path: Path) -> None:
        mission = parse_mission(_constrained_mission())
        planner = MissionPlanner()
        plan = planner.build(mission, constraint_context={"repository": tmp_path / "repo"})
        assert plan.valid is False
        assert any("repository" in e.lower() for e in plan.errors)

    def test_planner_build_no_constraints(self) -> None:
        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)
        assert plan.valid is True

    def test_planner_build_passing_constraints(self, tmp_path: Path) -> None:
        data = _constrained_mission()
        data["repository"] = str(tmp_path)
        data["working_directory"] = str(tmp_path)
        mission = parse_mission(data)
        planner = MissionPlanner()
        plan = planner.build(mission, constraint_context={
            "repository": tmp_path,
            "working_directory": tmp_path,
        })
        assert plan.valid is True

    def test_planner_build_runtime_version_constraint(self) -> None:
        data = _minimal_mission()
        data["constraints"] = ["runtime_version"]
        mission = parse_mission(data)
        planner = MissionPlanner()
        plan = planner.build(mission)
        assert plan.valid is True


# ---------------------------------------------------------------------------
# CLI Integration Tests
# ---------------------------------------------------------------------------

class TestConstraintsCLI:
    def test_constraints_json(self, tmp_path: Path, capsys) -> None:
        from argparse import Namespace
        from hermes_v01.mission_runner_cli import cmd_constraints

        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(_minimal_mission()), encoding="utf-8")

        args = Namespace(mission_file=str(mission_file), repository=None, cwd=None, json=True)
        result = cmd_constraints(args)
        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert "total" in data
        assert "results" in data

    def test_constraints_text(self, tmp_path: Path, capsys) -> None:
        from argparse import Namespace
        from hermes_v01.mission_runner_cli import cmd_constraints

        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(_minimal_mission()), encoding="utf-8")

        args = Namespace(mission_file=str(mission_file), repository=None, cwd=None, json=False)
        result = cmd_constraints(args)
        assert result == 0
        output = capsys.readouterr().out
        assert "satisfied" in output

    def test_constraints_with_repository(self, tmp_path: Path, capsys) -> None:
        from argparse import Namespace
        from hermes_v01.mission_runner_cli import cmd_constraints

        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(_constrained_mission()), encoding="utf-8")

        args = Namespace(
            mission_file=str(mission_file),
            repository=str(tmp_path / "nonexistent"),
            cwd=str(tmp_path),
            json=True,
        )
        result = cmd_constraints(args)
        assert result == 1

    def test_constraints_invalid_file(self, tmp_path: Path, capsys) -> None:
        from argparse import Namespace
        from hermes_v01.mission_runner_cli import cmd_constraints

        args = Namespace(mission_file=str(tmp_path / "nonexistent.json"), repository=None, cwd=None, json=True)
        result = cmd_constraints(args)
        assert result == 1
