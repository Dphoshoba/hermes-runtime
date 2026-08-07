from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hermes_v01.capabilities import (
    CapabilityMetadata,
    CapabilityRegistry,
    CapabilityState,
    LocalExecutorPlugin,
    PluginDiscovery,
    CapabilityManager,
)


def test_capability_metadata_defaults(tmp_path: Path) -> None:
    metadata = CapabilityMetadata(
        name="test",
        version="1.0.0",
        description="Test capability",
        capability_type="executor",
        entry_point="module:Class",
        required_runtime_version="0.7.0",
    )
    assert metadata.name == "test"
    assert metadata.enabled is True
    assert metadata.dependencies == ()
    assert metadata.metadata == {}


def test_capability_metadata_custom(tmp_path: Path) -> None:
    metadata = CapabilityMetadata(
        name="test",
        version="2.0.0",
        description="Test",
        capability_type="validator",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
        dependencies=("dep1", "dep2"),
        enabled=False,
        metadata={"key": "value"},
    )
    assert metadata.dependencies == ("dep1", "dep2")
    assert metadata.enabled is False
    assert metadata.metadata == {"key": "value"}


def test_capability_metadata_invalid_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown capability_type"):
        CapabilityMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            capability_type="invalid",
            entry_point="mod:Cls",
            required_runtime_version="0.7.0",
        )


def test_registry_register_and_get(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    metadata = CapabilityMetadata(
        name="test",
        version="1.0.0",
        description="Test",
        capability_type="executor",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
    )
    state = registry.register(metadata)
    assert state.metadata.name == "test"
    assert state.health_status == "UNKNOWN"
    assert registry.get("test") == state


def test_registry_duplicate_rejection(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    metadata = CapabilityMetadata(
        name="test",
        version="1.0.0",
        description="Test",
        capability_type="executor",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
    )
    registry.register(metadata)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(metadata)


def test_registry_list_filtering(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    for i, cap_type in enumerate(("executor", "validator", "provider")):
        registry.register(CapabilityMetadata(
            name=f"cap-{i}",
            version="1.0.0",
            description="Test",
            capability_type=cap_type,
            entry_point="mod:Cls",
            required_runtime_version="0.7.0",
        ))
    registry.register(CapabilityMetadata(
        name="disabled",
        version="1.0.0",
        description="Test",
        capability_type="executor",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
        enabled=False,
    ))

    all_caps = registry.list()
    assert len(all_caps) == 4

    executors = registry.list(capability_type="executor")
    assert len(executors) == 2
    assert all(c.metadata.capability_type == "executor" for c in executors)

    enabled = registry.list(enabled_only=True)
    assert len(enabled) == 3
    assert all(c.metadata.enabled for c in enabled)

    executor_enabled = registry.list(capability_type="executor", enabled_only=True)
    assert len(executor_enabled) == 1


def test_registry_enable_disable_persistence(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    registry = CapabilityRegistry(path)
    registry.register(CapabilityMetadata(
        name="test",
        version="1.0.0",
        description="Test",
        capability_type="executor",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
    ))
    registry.disable("test")
    assert registry.get("test").metadata.enabled is False

    # Reload from disk
    registry2 = CapabilityRegistry(path)
    assert registry2.get("test").metadata.enabled is False

    registry2.enable("test")
    assert registry2.get("test").metadata.enabled is True


def test_registry_health_update(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    registry.register(CapabilityMetadata(
        name="test",
        version="1.0.0",
        description="Test",
        capability_type="executor",
        entry_point="mod:Cls",
        required_runtime_version="0.7.0",
    ))
    updated = registry.update_health("test", "HEALTHY")
    assert updated.health_status == "HEALTHY"
    assert updated.last_health_check is not None


def test_plugin_discovery_loads_metadata(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "cap1.json").write_text(json.dumps({
        "name": "cap1",
        "version": "1.0.0",
        "description": "Cap 1",
        "capability_type": "executor",
        "entry_point": "mod:Cls",
        "required_runtime_version": "0.7.0",
    }))
    (plugin_dir / "cap2.json").write_text(json.dumps({
        "name": "cap2",
        "version": "2.0.0",
        "description": "Cap 2",
        "capability_type": "validator",
        "entry_point": "mod:Cls2",
        "required_runtime_version": "0.7.0",
    }))
    (plugin_dir / "invalid.json").write_text("{not json")

    discovery = PluginDiscovery([plugin_dir])
    caps = discovery.discover()
    assert len(caps) == 2
    assert {c.name for c in caps} == {"cap1", "cap2"}


def test_local_executor_plugin(tmp_path: Path) -> None:
    executor = LocalExecutorPlugin()
    assert executor.name == "local"
    healthy, error = executor.health_check()
    assert healthy is True
    assert error is None

    result = executor.execute(["echo", "hello"], tmp_path)
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_capability_manager_builtin_executor(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    manager = CapabilityManager(registry, [])
    executor = manager.get_executor("local")
    assert isinstance(executor, LocalExecutorPlugin)
    assert executor.name == "local"


def test_capability_manager_discover_and_register(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "custom.json").write_text(json.dumps({
        "name": "custom",
        "version": "1.0.0",
        "description": "Custom executor",
        "capability_type": "executor",
        "entry_point": "hermes_v01.capabilities:LocalExecutorPlugin",
        "required_runtime_version": "0.7.0",
    }))

    registry = CapabilityRegistry(tmp_path / "registry.json")
    manager = CapabilityManager(registry, [plugin_dir])
    registered = manager.discover_and_register()
    assert "custom" in registered
    assert registry.get("custom").metadata.name == "custom"


def test_capability_manager_health_check(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.json")
    manager = CapabilityManager(registry, [])
    state = manager.check_health("local")
    assert state.health_status == "HEALTHY"
    assert state.health_error is None


def test_capability_manager_check_all(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "exec1.json").write_text(json.dumps({
        "name": "exec1",
        "version": "1.0.0",
        "description": "Exec 1",
        "capability_type": "executor",
        "entry_point": "hermes_v01.capabilities:LocalExecutorPlugin",
        "required_runtime_version": "0.7.0",
    }))
    (plugin_dir / "validator1.json").write_text(json.dumps({
        "name": "validator1",
        "version": "1.0.0",
        "description": "Validator 1",
        "capability_type": "validator",
        "entry_point": "mod:Cls",
        "required_runtime_version": "0.7.0",
    }))

    registry = CapabilityRegistry(tmp_path / "registry.json")
    manager = CapabilityManager(registry, [plugin_dir])
    manager.discover_and_register()

    results = manager.check_all_health()
    assert len(results) == 3
    # local is built-in, exec1 and validator1 are discovered
    names = {r.metadata.name for r in results}
    assert "local" in names
    assert "exec1" in names
    assert "validator1" in names


def test_runtime_with_custom_executor(tmp_path: Path) -> None:
    """Test that runtime can use a custom executor via capability manager."""
    from hermes_v01.runtime import run_pipeline
    from hermes_v01.capabilities import CapabilityManager, CapabilityRegistry

    registry = CapabilityRegistry(tmp_path / "registry.json")
    manager = CapabilityManager(registry, [])
    executor = manager.get_executor("local")

    # This should work with the local executor
    runtime_root = tmp_path / "runtime"
    repository = tmp_path / "repo"
    working_dir = tmp_path / "work"
    runtime_root.mkdir()
    repository.mkdir()
    working_dir.mkdir()

    result = run_pipeline(
        ["echo", "test"],
        runtime_root=runtime_root,
        repository=repository,
        working_directory=working_dir,
        executor=executor,
    )
    assert result.status == "COMPLETED"
    assert result.exit_code == 0