from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

TASK_STATES = (
    "READY",
    "RUNNING",
    "BLOCKED",
    "OBSERVED",
    "VERIFICATION_PENDING",
    "VERIFIED",
    "COMPLETE",
)

TERMINAL_TASK_STATES = {"VERIFIED", "COMPLETE"}


@dataclass(frozen=True)
class WorkItem:
    task_id: str
    title: str
    priority: int = 100
    dependencies: tuple[str, ...] = ()
    state: str = "BLOCKED"
    attempts: int = 0
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.state not in TASK_STATES:
            raise ValueError(f"unknown task state: {self.state}")
        if self.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if self.task_id in self.dependencies:
            raise ValueError("a task cannot depend on itself")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dependencies"] = list(self.dependencies)
        return data


@dataclass(frozen=True)
class WorkQueueState:
    schema_version: str
    revision: int
    items: tuple[WorkItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "items": [item.as_dict() for item in self.items],
        }


class WorkQueueStateStore:
    """Atomically persists work-queue state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> WorkQueueState | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = tuple(
                WorkItem(
                    **{
                        **item,
                        "dependencies": tuple(item.get("dependencies", ())),
                    }
                )
                for item in raw.get("items", ())
            )
            return WorkQueueState(
                schema_version=raw["schema_version"],
                revision=int(raw["revision"]),
                items=items,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid work queue state: {self.path}") from exc

    def save(self, state: WorkQueueState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.as_dict(), indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


class WorkQueueManager:
    """Deterministic, restart-safe manager for Program III engineering tasks."""

    def __init__(self, *, state_store: WorkQueueStateStore, items: Iterable[WorkItem] = ()) -> None:
        self._state_store = state_store
        loaded = state_store.load()
        if loaded is not None:
            self._state = self._normalize(loaded)
        else:
            initial = tuple(items)
            self._validate_graph(initial)
            self._state = self._normalize(
                WorkQueueState(schema_version="1", revision=0, items=initial)
            )
            self._state_store.save(self._state)

    @property
    def state(self) -> WorkQueueState:
        return self._state

    def items(self) -> tuple[WorkItem, ...]:
        return self._state.items

    def get(self, task_id: str) -> WorkItem:
        for item in self._state.items:
            if item.task_id == task_id:
                return item
        raise KeyError(task_id)

    def next_ready(self) -> WorkItem | None:
        ready = [item for item in self._state.items if item.state == "READY"]
        if not ready:
            return None
        return min(ready, key=lambda item: (item.priority, item.task_id))

    def dispatch_next(self) -> WorkItem | None:
        item = self.next_ready()
        if item is None:
            return None
        return self.transition(item.task_id, "RUNNING", increment_attempts=True)

    def transition(
        self,
        task_id: str,
        state: str,
        *,
        last_error: str | None = None,
        increment_attempts: bool = False,
    ) -> WorkItem:
        if state not in TASK_STATES:
            raise ValueError(f"unknown task state: {state}")
        current = self.get(task_id)
        if current.state in TERMINAL_TASK_STATES and state not in TERMINAL_TASK_STATES:
            raise ValueError(f"cannot move terminal task {task_id} back to {state}")
        if current.state == "RUNNING" and state == "RUNNING":
            raise ValueError(f"task already running: {task_id}")

        updated = replace(
            current,
            state=state,
            attempts=current.attempts + (1 if increment_attempts else 0),
            last_error=last_error,
        )
        self._replace_item(updated)
        return self.get(task_id)

    def mark_observed(self, task_id: str) -> WorkItem:
        return self.transition(task_id, "OBSERVED")

    def mark_verification_pending(self, task_id: str) -> WorkItem:
        return self.transition(task_id, "VERIFICATION_PENDING")

    def record_independent_verification(self, task_id: str) -> WorkItem:
        current = self.get(task_id)
        if current.state != "VERIFICATION_PENDING":
            raise ValueError("independent verification requires VERIFICATION_PENDING")
        return self.transition(task_id, "VERIFIED")

    def mark_complete(self, task_id: str) -> WorkItem:
        current = self.get(task_id)
        if current.state not in {"VERIFIED", "COMPLETE"}:
            raise ValueError("completion requires independently VERIFIED state")
        return self.transition(task_id, "COMPLETE")

    def refresh(self) -> WorkQueueState:
        normalized = self._normalize(self._state)
        if normalized != self._state:
            self._persist(normalized)
        return self._state

    def summary(self) -> dict[str, list[str]]:
        result = {state: [] for state in TASK_STATES}
        for item in sorted(self._state.items, key=lambda value: (value.priority, value.task_id)):
            result[item.state].append(item.task_id)
        return result

    def _replace_item(self, updated: WorkItem) -> None:
        items = tuple(updated if item.task_id == updated.task_id else item for item in self._state.items)
        next_state = WorkQueueState(
            schema_version=self._state.schema_version,
            revision=self._state.revision + 1,
            items=items,
        )
        self._persist(self._normalize(next_state))

    def _persist(self, state: WorkQueueState) -> None:
        self._validate_graph(state.items)
        self._state_store.save(state)
        self._state = state

    @staticmethod
    def _normalize(state: WorkQueueState) -> WorkQueueState:
        by_id = {item.task_id: item for item in state.items}
        normalized: list[WorkItem] = []
        for item in state.items:
            if item.state in {"RUNNING", "OBSERVED", "VERIFICATION_PENDING", "VERIFIED", "COMPLETE"}:
                normalized.append(item)
                continue
            dependencies_satisfied = all(
                by_id[dependency].state in TERMINAL_TASK_STATES
                for dependency in item.dependencies
            )
            desired = "READY" if dependencies_satisfied else "BLOCKED"
            normalized.append(replace(item, state=desired))
        return WorkQueueState(
            schema_version=state.schema_version,
            revision=state.revision,
            items=tuple(normalized),
        )

    @staticmethod
    def _validate_graph(items: Iterable[WorkItem]) -> None:
        item_tuple = tuple(items)
        by_id: Mapping[str, WorkItem] = {item.task_id: item for item in item_tuple}
        if len(by_id) != len(item_tuple):
            raise ValueError("duplicate task_id")
        for item in item_tuple:
            unknown = [dependency for dependency in item.dependencies if dependency not in by_id]
            if unknown:
                raise ValueError(f"unknown dependencies for {item.task_id}: {unknown}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise ValueError("cyclic task dependencies")
            visiting.add(task_id)
            for dependency in by_id[task_id].dependencies:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in by_id:
            visit(task_id)
