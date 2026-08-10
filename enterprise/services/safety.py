"""Safety boundary enforcement — read-only operations only."""

from __future__ import annotations

from typing import Any


FORBIDDEN_OPERATIONS = frozenset({
    "modify_source_code",
    "create_branch",
    "commit",
    "push",
    "create_pull_request",
    "merge",
    "modify_github_settings",
    "modify_workflows",
    "execute_mission",
})


def is_operation_allowed(operation: str) -> bool:
    return operation not in FORBIDDEN_OPERATIONS


def check_safety_boundary(operation: str) -> dict[str, Any]:
    allowed = is_operation_allowed(operation)
    return {
        "operation": operation,
        "allowed": allowed,
        "reason": "Read-only trial mode" if not allowed else "Operation permitted",
    }


def enforce_read_only(operation: str) -> None:
    if not is_operation_allowed(operation):
        raise ValueError(
            f"Forbidden operation '{operation}' during operational trial. "
            f"Trial mode is read-only with respect to target repositories."
        )
