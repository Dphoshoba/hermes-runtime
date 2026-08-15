"""Comprehensive tests for the Mission Type Registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evosia.mission import (
    Mission,
    MissionPlanner,
    MissionTask,
    RetryPolicy,
    parse_mission,
)
from evosia.mission_types import (
    CITask,
    DependencyUpgrade,
    DocumentationRefresh,
    MissionType,
    MissionTypeMetadata,
    MissionTypeRegistry,
    PerformanceAudit,
    ReleasePreparation,
    RepositoryMaintenance,
    SecurityAudit,
    register_built_in_types,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CustomMissionType(MissionType):
    """Test-only custom mission type."""
    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="custom-test-type",
            version="1.0.0",
            description="A custom test mission type",
            category="testing",
            required_capabilities=("custom-cap",),
            default_constraints=("custom constraint",),
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if len(mission.tasks) > 5:
            warnings.append("custom type warns on >5 tasks")
        return errors, warnings

    def build_tasks(self, mission: Mission, **kwargs: Any) -> list[dict[str, Any]]:
        return [t.as_dict() for t in mission.tasks]


class FailingValidationType(MissionType):
    """Test type that always fails validation."""
    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="failing-validation",
            version="1.0.0",
            description="Always fails validation",
            category="testing",
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        return ["always fails", "second error"], []


def _minimal_mission() -> dict:
    return {
        "mission_id": "type-test-001",
        "title": "Type Test Mission",
        "description": "Test mission for type registry",
        "tasks": [
            {"title": "Task 1", "command": ["echo", "hello"]},
        ],
    }


def _reset_registry() -> MissionTypeRegistry:
    """Reset and return a fresh registry."""
    MissionTypeRegistry.reset()
    return MissionTypeRegistry.instance()


# ---------------------------------------------------------------------------
# MissionTypeMetadata Tests
# ---------------------------------------------------------------------------

class TestMissionTypeMetadata:
    def test_metadata_fields(self) -> None:
        meta = MissionTypeMetadata(
            name="test",
            version="1.0.0",
            description="Test type",
            category="testing",
        )
        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.description == "Test type"
        assert meta.category == "testing"
        assert meta.required_capabilities == ()
        assert meta.default_constraints == ()
        assert meta.supported_task_patterns == ()

    def test_metadata_as_dict(self) -> None:
        meta = MissionTypeMetadata(
            name="test",
            version="1.0.0",
            description="Test type",
            category="security",
            required_capabilities=("cap1", "cap2"),
            default_constraints=("c1",),
            supported_task_patterns=("scan", "audit"),
            metadata={"key": "value"},
        )
        d = meta.as_dict()
        assert d["name"] == "test"
        assert d["category"] == "security"
        assert d["required_capabilities"] == ["cap1", "cap2"]
        assert d["default_constraints"] == ["c1"]
        assert d["supported_task_patterns"] == ["scan", "audit"]
        assert d["metadata"] == {"key": "value"}

    def test_metadata_defaults(self) -> None:
        meta = MissionTypeMetadata(
            name="t", version="1", description="d", category="c"
        )
        d = meta.as_dict()
        assert d["required_capabilities"] == []
        assert d["default_constraints"] == []
        assert d["supported_task_patterns"] == []
        assert d["metadata"] == {}

    def test_metadata_deterministic(self) -> None:
        args = dict(name="t", version="1", description="d", category="c")
        m1 = MissionTypeMetadata(**args)
        m2 = MissionTypeMetadata(**args)
        assert m1.as_dict() == m2.as_dict()


# ---------------------------------------------------------------------------
# MissionType ABC Tests
# ---------------------------------------------------------------------------

class TestMissionTypeABC:
    def test_custom_type_metadata(self) -> None:
        mt = CustomMissionType()
        meta = mt.get_metadata()
        assert meta.name == "custom-test-type"
        assert meta.category == "testing"
        assert meta.required_capabilities == ("custom-cap",)

    def test_custom_type_validation(self) -> None:
        mt = CustomMissionType()
        mission = parse_mission(_minimal_mission())
        errors, warnings = mt.validate_mission(mission)
        assert errors == []
        assert warnings == []

    def test_custom_type_validation_warning(self) -> None:
        mt = CustomMissionType()
        data = _minimal_mission()
        data["tasks"] = [{"title": f"Task {i}", "command": ["echo", str(i)]} for i in range(6)]
        mission = parse_mission(data)
        errors, warnings = mt.validate_mission(mission)
        assert len(warnings) == 1
        assert ">5 tasks" in warnings[0]

    def test_custom_type_build_tasks(self) -> None:
        mt = CustomMissionType()
        mission = parse_mission(_minimal_mission())
        tasks = mt.build_tasks(mission)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Task 1"

    def test_default_validate_returns_empty(self) -> None:
        class MinimalType(MissionType):
            def get_metadata(self) -> MissionTypeMetadata:
                return MissionTypeMetadata(
                    name="minimal", version="1", description="d", category="c"
                )
        mt = MinimalType()
        mission = parse_mission(_minimal_mission())
        errors, warnings = mt.validate_mission(mission)
        assert errors == []
        assert warnings == []

    def test_get_default_constraints(self) -> None:
        mt = CustomMissionType()
        constraints = mt.get_default_constraints()
        assert constraints == ("custom constraint",)

    def test_get_required_capabilities(self) -> None:
        mt = CustomMissionType()
        caps = mt.get_required_capabilities()
        assert caps == ("custom-cap",)


# ---------------------------------------------------------------------------
# MissionTypeRegistry Tests
# ---------------------------------------------------------------------------

class TestMissionTypeRegistry:
    def test_singleton(self) -> None:
        r1 = MissionTypeRegistry.instance()
        r2 = MissionTypeRegistry.instance()
        assert r1 is r2

    def test_reset(self) -> None:
        r1 = MissionTypeRegistry.instance()
        MissionTypeRegistry.reset()
        r2 = MissionTypeRegistry.instance()
        assert r1 is not r2

    def test_register_and_get(self) -> None:
        registry = _reset_registry()
        mt = CustomMissionType()
        registry.register(mt)
        assert registry.get("custom-test-type") is mt

    def test_register_duplicate_raises(self) -> None:
        registry = _reset_registry()
        mt = CustomMissionType()
        registry.register(mt)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(mt)

    def test_register_empty_name_raises(self) -> None:
        registry = _reset_registry()
        class EmptyNameType(MissionType):
            def get_metadata(self) -> MissionTypeMetadata:
                return MissionTypeMetadata(
                    name="", version="1", description="d", category="c"
                )
        with pytest.raises(ValueError, match="name must not be empty"):
            registry.register(EmptyNameType())

    def test_unregister(self) -> None:
        registry = _reset_registry()
        mt = CustomMissionType()
        registry.register(mt)
        registry.unregister("custom-test-type")
        assert not registry.is_registered("custom-test-type")

    def test_unregister_nonexistent_raises(self) -> None:
        registry = _reset_registry()
        with pytest.raises(KeyError, match="not found"):
            registry.unregister("nonexistent")

    def test_get_nonexistent_raises(self) -> None:
        registry = _reset_registry()
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_get_metadata(self) -> None:
        registry = _reset_registry()
        mt = CustomMissionType()
        registry.register(mt)
        meta = registry.get_metadata("custom-test-type")
        assert meta.name == "custom-test-type"

    def test_get_metadata_nonexistent_raises(self) -> None:
        registry = _reset_registry()
        with pytest.raises(KeyError, match="not found"):
            registry.get_metadata("nonexistent")

    def test_is_registered(self) -> None:
        registry = _reset_registry()
        assert not registry.is_registered("custom-test-type")
        registry.register(CustomMissionType())
        assert registry.is_registered("custom-test-type")

    def test_list_types(self) -> None:
        registry = _reset_registry()
        registry.register(CustomMissionType())
        registry.register(FailingValidationType())
        types = registry.list_types()
        assert len(types) == 2
        names = [t.name for t in types]
        assert "custom-test-type" in names
        assert "failing-validation" in names

    def test_list_types_by_category(self) -> None:
        registry = _reset_registry()
        registry.register(CustomMissionType())
        registry.register(FailingValidationType())
        testing_types = registry.list_types(category="testing")
        assert len(testing_types) == 2
        other_types = registry.list_types(category="security")
        assert len(other_types) == 0

    def test_list_names(self) -> None:
        registry = _reset_registry()
        registry.register(CustomMissionType())
        registry.register(FailingValidationType())
        names = registry.list_names()
        assert names == ["custom-test-type", "failing-validation"]

    def test_list_sorted(self) -> None:
        registry = _reset_registry()
        registry.register(FailingValidationType())
        registry.register(CustomMissionType())
        names = registry.list_names()
        assert names == ["custom-test-type", "failing-validation"]


# ---------------------------------------------------------------------------
# Built-in Types Tests
# ---------------------------------------------------------------------------

class TestBuiltInTypes:
    def test_register_built_in_types(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        names = registry.list_names()
        assert "repository-maintenance" in names
        assert "dependency-upgrade" in names
        assert "documentation-refresh" in names
        assert "security-audit" in names
        assert "performance-audit" in names
        assert "release-preparation" in names
        assert "ci-verification" in names

    def test_register_built_in_types_idempotent(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        count_before = len(registry.list_names())
        register_built_in_types(registry)
        count_after = len(registry.list_names())
        assert count_before == count_after

    def test_repository_maintenance(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("repository-maintenance")
        assert isinstance(mt, RepositoryMaintenance)
        meta = mt.get_metadata()
        assert meta.category == "maintenance"
        assert meta.version == "1.0.0"

    def test_dependency_upgrade(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("dependency-upgrade")
        assert isinstance(mt, DependencyUpgrade)

    def test_documentation_refresh(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("documentation-refresh")
        assert isinstance(mt, DocumentationRefresh)

    def test_security_audit(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("security-audit")
        assert isinstance(mt, SecurityAudit)
        meta = mt.get_metadata()
        assert "security-scanner" in meta.required_capabilities

    def test_performance_audit(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("performance-audit")
        assert isinstance(mt, PerformanceAudit)

    def test_release_preparation(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("release-preparation")
        assert isinstance(mt, ReleasePreparation)

    def test_ci_verification(self) -> None:
        registry = _reset_registry()
        register_built_in_types(registry)
        mt = registry.get("ci-verification")
        assert isinstance(mt, CITask)


# ---------------------------------------------------------------------------
# Built-in Type Validation Tests
# ---------------------------------------------------------------------------

class TestBuiltInTypeValidation:
    def test_repository_maintenance_warns_without_repo(self) -> None:
        mt = RepositoryMaintenance()
        mission = parse_mission(_minimal_mission())
        errors, warnings = mt.validate_mission(mission)
        assert errors == []
        assert any("repository" in w.lower() for w in warnings)

    def test_repository_maintenance_no_warn_with_repo(self) -> None:
        mt = RepositoryMaintenance()
        data = _minimal_mission()
        data["repository"] = "/tmp/repo"
        mission = parse_mission(data)
        errors, warnings = mt.validate_mission(mission)
        assert not any("repository" in w.lower() for w in warnings)

    def test_dependency_upgrade_warns_without_repo(self) -> None:
        mt = DependencyUpgrade()
        mission = parse_mission(_minimal_mission())
        errors, warnings = mt.validate_mission(mission)
        assert any("repository" in w.lower() for w in warnings)

    def test_release_preparation_warns_without_version(self) -> None:
        mt = ReleasePreparation()
        mission = parse_mission(_minimal_mission())
        errors, warnings = mt.validate_mission(mission)
        assert any("version" in w.lower() for w in warnings)

    def test_release_preparation_no_warn_with_version(self) -> None:
        mt = ReleasePreparation()
        data = _minimal_mission()
        data["metadata"] = {"version": "1.0.0"}
        data["repository"] = "/tmp/repo"
        mission = parse_mission(data)
        errors, warnings = mt.validate_mission(mission)
        assert not any("version" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# CLI Integration Tests
# ---------------------------------------------------------------------------

class TestMissionTypeCLI:
    def test_types_list(self, capsys) -> None:
        from evosia.mission_runner_cli import cmd_types

        class Args:
            category = None
            json = False
        result = cmd_types(Args())
        assert result == 0
        output = capsys.readouterr().out
        assert "repository-maintenance" in output

    def test_types_json(self, capsys) -> None:
        from evosia.mission_runner_cli import cmd_types

        class Args:
            category = None
            json = True
        result = cmd_types(Args())
        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)
        names = [t["name"] for t in data]
        assert "repository-maintenance" in names

    def test_types_filter_category(self, capsys) -> None:
        from evosia.mission_runner_cli import cmd_types

        class Args:
            category = "security"
            json = True
        result = cmd_types(Args())
        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["name"] == "security-audit"

    def test_type_show(self, capsys) -> None:
        from evosia.mission_runner_cli import cmd_type_show

        class Args:
            type_name = "security-audit"
        result = cmd_type_show(Args())
        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["name"] == "security-audit"
        assert data["category"] == "security"

    def test_type_show_nonexistent(self, capsys) -> None:
        from evosia.mission_runner_cli import cmd_type_show

        class Args:
            type_name = "nonexistent-type"
        result = cmd_type_show(Args())
        assert result == 1


# ---------------------------------------------------------------------------
# Runner Integration Tests
# ---------------------------------------------------------------------------

class TestRunnerMissionTypeIntegration:
    def test_runner_accepts_mission_type(self) -> None:
        from evosia.mission_runner import MissionRunner
        runner = MissionRunner(
            runtime_root=Path("/tmp/r"),
            repository=Path("/tmp/r"),
            working_directory=Path("/tmp/w"),
            queue_path=Path("/tmp/q.json"),
            mission_type_name="security-audit",
        )
        assert runner.mission_type_name == "security-audit"

    def test_runner_default_mission_type(self) -> None:
        from evosia.mission_runner import MissionRunner
        runner = MissionRunner(
            runtime_root=Path("/tmp/r"),
            repository=Path("/tmp/r"),
            working_directory=Path("/tmp/w"),
            queue_path=Path("/tmp/q.json"),
        )
        assert runner.mission_type_name is None

    def test_report_includes_mission_type(self, tmp_path: Path, monkeypatch) -> None:
        from evosia.mission_runner import MissionRunner
        from tests.test_mission_runner import _mock_hermes_binaries, _setup_runner_env

        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env, mission_type_name="ci-verification")

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.mission_type == "ci-verification"
        d = report.as_dict()
        assert d["mission_type"] == "ci-verification"
