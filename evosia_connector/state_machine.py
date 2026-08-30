"""Connector state machine — deterministic UX states for desktop/tray."""

from __future__ import annotations

from enum import Enum


class ConnectorState(Enum):
    """Top-level Connector UX states.

    These are UX/runtime states only — not authority states.
    """
    STARTING = "starting"
    NOT_CONNECTED = "not_connected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    NO_PROJECTS = "no_projects"
    READY = "ready"
    REVIEW_QUEUED = "review_queued"
    REVIEW_IN_PROGRESS = "review_in_progress"
    REVIEW_COMPLETE = "review_complete"
    REVIEW_FAILED = "review_failed"
    OFFLINE = "offline"
    ERROR = "error"


# Valid state transitions
VALID_TRANSITIONS = {
    ConnectorState.STARTING: [
        ConnectorState.NOT_CONNECTED,
        ConnectorState.CONNECTED,
        ConnectorState.ERROR,
    ],
    ConnectorState.NOT_CONNECTED: [
        ConnectorState.CONNECTING,
        ConnectorState.ERROR,
    ],
    ConnectorState.CONNECTING: [
        ConnectorState.CONNECTED,
        ConnectorState.NOT_CONNECTED,
        ConnectorState.ERROR,
    ],
    ConnectorState.CONNECTED: [
        ConnectorState.NO_PROJECTS,
        ConnectorState.READY,
        ConnectorState.NOT_CONNECTED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.NO_PROJECTS: [
        ConnectorState.READY,
        ConnectorState.NOT_CONNECTED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.READY: [
        ConnectorState.REVIEW_QUEUED,
        ConnectorState.NO_PROJECTS,
        ConnectorState.NOT_CONNECTED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.REVIEW_QUEUED: [
        ConnectorState.REVIEW_IN_PROGRESS,
        ConnectorState.REVIEW_FAILED,
        ConnectorState.READY,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.REVIEW_IN_PROGRESS: [
        ConnectorState.REVIEW_COMPLETE,
        ConnectorState.REVIEW_FAILED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.REVIEW_COMPLETE: [
        ConnectorState.READY,
        ConnectorState.REVIEW_QUEUED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.REVIEW_FAILED: [
        ConnectorState.READY,
        ConnectorState.REVIEW_QUEUED,
        ConnectorState.OFFLINE,
        ConnectorState.ERROR,
    ],
    ConnectorState.OFFLINE: [
        ConnectorState.CONNECTED,
        ConnectorState.NOT_CONNECTED,
        ConnectorState.ERROR,
    ],
    ConnectorState.ERROR: [
        ConnectorState.STARTING,
        ConnectorState.NOT_CONNECTED,
    ],
}


def can_transition(current: ConnectorState, target: ConnectorState) -> bool:
    """Check if a state transition is valid."""
    return target in VALID_TRANSITIONS.get(current, [])


def get_initial_state(has_credential: bool, has_projects: bool) -> ConnectorState:
    """Determine initial state based on credential and project status."""
    if not has_credential:
        return ConnectorState.NOT_CONNECTED
    if not has_projects:
        return ConnectorState.CONNECTED
    return ConnectorState.READY
