"""Shared test fixtures for the Hermes Runtime test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_v01.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


@pytest.fixture
def minimal_mission() -> dict:
    """A minimal valid mission for testing."""
    return {
        "mission_id": "test-mission-001",
        "title": "Test Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
        ],
    }


@pytest.fixture
def multi_task_mission() -> dict:
    """A mission with multiple independent tasks."""
    return {
        "mission_id": "multi-test-001",
        "title": "Multi Task Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"]},
            {"title": "Task C", "command": ["echo", "c"]},
        ],
    }


@pytest.fixture
def diamond_mission() -> dict:
    """A mission with diamond dependency pattern (A -> B, A -> C -> D)."""
    return {
        "mission_id": "diamond-test-001",
        "title": "Diamond Dependency Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"], "dependencies": ["task-0"]},
            {"title": "Task C", "command": ["echo", "c"], "dependencies": ["task-0"]},
            {"title": "Task D", "command": ["echo", "d"], "dependencies": ["task-1", "task-2"]},
        ],
    }


@pytest.fixture
def chain_mission() -> dict:
    """A mission with chained dependencies (A -> B -> C)."""
    return {
        "mission_id": "chain-test-001",
        "title": "Chain Dependency Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"], "dependencies": ["task-0"]},
            {"title": "Task C", "command": ["echo", "c"], "dependencies": ["task-1"]},
        ],
    }


@pytest.fixture
def work_item_factory():
    """Factory for creating WorkItem instances with sensible defaults."""
    def _factory(
        task_id: str,
        state: str = "READY",
        dependencies: tuple[str, ...] = (),
        max_retries: int = 3,
        retryable: bool = True,
    ) -> WorkItem:
        return WorkItem(
            task_id=task_id,
            title=f"Task {task_id}",
            state=state,
            dependencies=dependencies,
            max_retries=max_retries,
            retryable=retryable,
        )
    return _factory


@pytest.fixture
def queue_factory(tmp_path: Path):
    """Factory for creating WorkQueueManager instances."""
    def _factory(items: list[WorkItem] | None = None) -> WorkQueueManager:
        store = WorkQueueStateStore(tmp_path / "queue.json")
        return WorkQueueManager(state_store=store, items=tuple(items or []))
    return _factory


@pytest.fixture
def runtime_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create standard runtime directory structure and return paths."""
    dirs = {}
    for name in ["runtime", "evidence", "reviews", "health", "runs", "state", "repo", "work"]:
        d = tmp_path / name
        d.mkdir()
        dirs[name] = d
    return dirs
