from __future__ import annotations

import json
import os
import tempfile
import importlib.util
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


CAPABILITY_TYPES = ("executor", "validator", "provider", "notifier")


@dataclass(frozen=True)
class CapabilityMetadata:
    name: str
    version: str
    description: str
    capability_type: str
    entry_point: str
    required_runtime_version: str
    dependencies: tuple[str, ...] = ()
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.version.strip():
            raise ValueError("version must not be empty")
        if self.capability_type not in CAPABILITY_TYPES:
            raise ValueError(f"unknown capability_type: {self.capability_type}")
        if not self.entry_point.strip():
            raise ValueError("entry_point must not be empty")
        if not self.required_runtime_version.strip():
            raise ValueError("required_runtime_version must not be empty")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dependencies"] = list(self.dependencies)
        return data


@dataclass(frozen=True)
class CapabilityState:
    metadata: CapabilityMetadata
    registered_at: str
    last_health_check: Optional[str] = None
    health_status: str = "UNKNOWN"
    health_error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "registered_at": self.registered_at,
            "last_health_check": self.last_health_check,
            "health_status": self.health_status,
            "health_error": self.health_error,
        }


class CapabilityRegistry:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path.expanduser().resolve()
        self._capabilities: dict[str, CapabilityState] = {}
        self._load()

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            for name, cap_data in data.get("capabilities", {}).items():
                metadata = CapabilityMetadata(**cap_data["metadata"])
                state = CapabilityState(
                    metadata=metadata,
                    registered_at=cap_data["registered_at"],
                    last_health_check=cap_data.get("last_health_check"),
                    health_status=cap_data.get("health_status", "UNKNOWN"),
                    health_error=cap_data.get("health_error"),
                )
                self._capabilities[name] = state
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": "1",
            "capabilities": {name: state.as_dict() for name, state in self._capabilities.items()},
        }
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self._state_path.name}.",
            suffix=".tmp",
            dir=str(self._state_path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._state_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def register(self, metadata: CapabilityMetadata) -> CapabilityState:
        if metadata.name in self._capabilities:
            raise ValueError(f"capability already registered: {metadata.name}")
        state = CapabilityState(
            metadata=metadata,
            registered_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        self._capabilities[metadata.name] = state
        self._save()
        return state

    def unregister(self, name: str) -> None:
        if name not in self._capabilities:
            raise KeyError(name)
        del self._capabilities[name]
        self._save()

    def get(self, name: str) -> CapabilityState:
        if name not in self._capabilities:
            raise KeyError(name)
        return self._capabilities[name]

    def list(self, capability_type: Optional[str] = None, enabled_only: bool = False) -> list[CapabilityState]:
        result = list(self._capabilities.values())
        if capability_type:
            result = [c for c in result if c.metadata.capability_type == capability_type]
        if enabled_only:
            result = [c for c in result if c.metadata.enabled]
        return sorted(result, key=lambda c: c.metadata.name)

    def enable(self, name: str) -> CapabilityState:
        state = self.get(name)
        if state.metadata.enabled:
            return state
        new_metadata = CapabilityMetadata(
            **{**state.metadata.as_dict(), "enabled": True}
        )
        new_state = CapabilityState(
            metadata=new_metadata,
            registered_at=state.registered_at,
            last_health_check=state.last_health_check,
            health_status=state.health_status,
            health_error=state.health_error,
        )
        self._capabilities[name] = new_state
        self._save()
        return new_state

    def disable(self, name: str) -> CapabilityState:
        state = self.get(name)
        if not state.metadata.enabled:
            return state
        new_metadata = CapabilityMetadata(
            **{**state.metadata.as_dict(), "enabled": False}
        )
        new_state = CapabilityState(
            metadata=new_metadata,
            registered_at=state.registered_at,
            last_health_check=state.last_health_check,
            health_status=state.health_status,
            health_error=state.health_error,
        )
        self._capabilities[name] = new_state
        self._save()
        return new_state

    def update_health(self, name: str, status: str, error: Optional[str] = None) -> CapabilityState:
        state = self.get(name)
        new_state = CapabilityState(
            metadata=state.metadata,
            registered_at=state.registered_at,
            last_health_check=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            health_status=status,
            health_error=error,
        )
        self._capabilities[name] = new_state
        self._save()
        return new_state


class PluginDiscovery:
    def __init__(self, plugin_dirs: list[Path]) -> None:
        self._plugin_dirs = [d.expanduser().resolve() for d in plugin_dirs]

    def discover(self) -> list[CapabilityMetadata]:
        capabilities: list[CapabilityMetadata] = []
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                continue
            for path in plugin_dir.glob("*.json"):
                try:
                    metadata = self._load_metadata(path)
                    if metadata:
                        capabilities.append(metadata)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return capabilities

    def _load_metadata(self, path: Path) -> Optional[CapabilityMetadata]:
        data = json.loads(path.read_text(encoding="utf-8"))
        required = ("name", "version", "description", "capability_type", "entry_point", "required_runtime_version")
        if not all(k in data for k in required):
            return None
        return CapabilityMetadata(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            capability_type=data["capability_type"],
            entry_point=data["entry_point"],
            required_runtime_version=data["required_runtime_version"],
            dependencies=tuple(data.get("dependencies", [])),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )


class ExecutorPlugin(ABC):
    @abstractmethod
    def execute(self, command: list[str], working_directory: Path, **kwargs) -> "ExecutionResult":
        pass

    @abstractmethod
    def health_check(self) -> tuple[bool, Optional[str]]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    artifacts: dict[str, str] = field(default_factory=dict)


class LocalExecutorPlugin(ExecutorPlugin):
    @property
    def name(self) -> str:
        return "local"

    def execute(self, command: list[str], working_directory: Path, **kwargs) -> ExecutionResult:
        result = subprocess.run(
            command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            **kwargs,
        )
        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def health_check(self) -> tuple[bool, Optional[str]]:
        return True, None


class CapabilityManager:
    def __init__(self, registry: CapabilityRegistry, plugin_dirs: list[Path]) -> None:
        self._registry = registry
        self._discovery = PluginDiscovery(plugin_dirs)
        self._executors: dict[str, ExecutorPlugin] = {"local": LocalExecutorPlugin()}
        try:
            self._registry.register(CapabilityMetadata(
                name="local",
                version="1.0.0",
                description="Built-in local subprocess executor",
                capability_type="executor",
                entry_point="hermes_v01.capabilities:LocalExecutorPlugin",
                required_runtime_version="0.7.0",
            ))
        except ValueError:
            pass

    def discover_and_register(self) -> list[str]:
        registered = []
        for metadata in self._discovery.discover():
            try:
                self._registry.register(metadata)
                registered.append(metadata.name)
            except ValueError:
                pass
        return registered

    def get_executor(self, name: str) -> ExecutorPlugin:
        if name in self._executors:
            return self._executors[name]
        state = self._registry.get(name)
        if state.metadata.capability_type != "executor":
            raise ValueError(f"capability {name} is not an executor")
        if not state.metadata.enabled:
            raise ValueError(f"executor {name} is disabled")
        plugin = self._load_executor(state.metadata.entry_point)
        self._executors[name] = plugin
        return plugin

    def _load_executor(self, entry_point: str) -> ExecutorPlugin:
        if ":" not in entry_point:
            raise ValueError(f"invalid entry_point format: {entry_point}")
        module_path, class_name = entry_point.rsplit(":", 1)
        spec = importlib.util.spec_from_file_location(module_path, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        executor_class = getattr(module, class_name, None)
        if executor_class is None or not issubclass(executor_class, ExecutorPlugin):
            raise ValueError(f"entry_point does not resolve to ExecutorPlugin subclass: {entry_point}")
        return executor_class()

    def check_health(self, name: str) -> CapabilityState:
        state = self._registry.get(name)
        if state.metadata.capability_type == "executor":
            try:
                executor = self.get_executor(name)
                healthy, error = executor.health_check()
                return self._registry.update_health(name, "HEALTHY" if healthy else "UNHEALTHY", error)
            except Exception as e:
                return self._registry.update_health(name, "UNHEALTHY", str(e))
        return self._registry.update_health(name, "UNKNOWN", "health check not implemented for this type")

    def check_all_health(self) -> list[CapabilityState]:
        results = []
        for state in self._registry.list():
            if state.metadata.enabled:
                results.append(self.check_health(state.metadata.name))
        return results