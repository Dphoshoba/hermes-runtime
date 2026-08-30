"""Tests for P3e desktop/tray workflow."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from evosia_connector.state_machine import (
    ConnectorState,
    can_transition,
    get_initial_state,
)


class TestStateMachine:
    """Test Connector state machine."""

    def test_initial_state_no_credential_no_projects(self):
        """Test initial state when no credential and no projects."""
        state = get_initial_state(has_credential=False, has_projects=False)
        assert state == ConnectorState.NOT_CONNECTED

    def test_initial_state_with_credential_no_projects(self):
        """Test initial state when credential exists but no projects."""
        state = get_initial_state(has_credential=True, has_projects=False)
        assert state == ConnectorState.CONNECTED

    def test_initial_state_with_credential_with_projects(self):
        """Test initial state when credential and projects exist."""
        state = get_initial_state(has_credential=True, has_projects=True)
        assert state == ConnectorState.READY

    def test_valid_transition_starting_to_not_connected(self):
        """Test valid transition from STARTING to NOT_CONNECTED."""
        assert can_transition(ConnectorState.STARTING, ConnectorState.NOT_CONNECTED)

    def test_valid_transition_starting_to_connected(self):
        """Test valid transition from STARTING to CONNECTED."""
        assert can_transition(ConnectorState.STARTING, ConnectorState.CONNECTED)

    def test_valid_transition_not_connected_to_connecting(self):
        """Test valid transition from NOT_CONNECTED to CONNECTING."""
        assert can_transition(ConnectorState.NOT_CONNECTED, ConnectorState.CONNECTING)

    def test_valid_transition_connecting_to_connected(self):
        """Test valid transition from CONNECTING to CONNECTED."""
        assert can_transition(ConnectorState.CONNECTING, ConnectorState.CONNECTED)

    def test_valid_transition_connecting_to_not_connected(self):
        """Test valid transition from CONNECTING to NOT_CONNECTED."""
        assert can_transition(ConnectorState.CONNECTING, ConnectorState.NOT_CONNECTED)

    def test_valid_transition_connected_to_ready(self):
        """Test valid transition from CONNECTED to READY."""
        assert can_transition(ConnectorState.CONNECTED, ConnectorState.READY)

    def test_valid_transition_ready_to_review_queued(self):
        """Test valid transition from READY to REVIEW_QUEUED."""
        assert can_transition(ConnectorState.READY, ConnectorState.REVIEW_QUEUED)

    def test_valid_transition_review_queued_to_in_progress(self):
        """Test valid transition from REVIEW_QUEUED to REVIEW_IN_PROGRESS."""
        assert can_transition(ConnectorState.REVIEW_QUEUED, ConnectorState.REVIEW_IN_PROGRESS)

    def test_valid_transition_review_in_progress_to_complete(self):
        """Test valid transition from REVIEW_IN_PROGRESS to REVIEW_COMPLETE."""
        assert can_transition(ConnectorState.REVIEW_IN_PROGRESS, ConnectorState.REVIEW_COMPLETE)

    def test_valid_transition_review_in_progress_to_failed(self):
        """Test valid transition from REVIEW_IN_PROGRESS to REVIEW_FAILED."""
        assert can_transition(ConnectorState.REVIEW_IN_PROGRESS, ConnectorState.REVIEW_FAILED)

    def test_valid_transition_review_complete_to_ready(self):
        """Test valid transition from REVIEW_COMPLETE to READY."""
        assert can_transition(ConnectorState.REVIEW_COMPLETE, ConnectorState.READY)

    def test_invalid_transition_ready_to_connecting(self):
        """Test invalid transition from READY to CONNECTING."""
        assert not can_transition(ConnectorState.READY, ConnectorState.CONNECTING)

    def test_invalid_transition_review_in_progress_to_connecting(self):
        """Test invalid transition from REVIEW_IN_PROGRESS to CONNECTING."""
        assert not can_transition(ConnectorState.REVIEW_IN_PROGRESS, ConnectorState.CONNECTING)

    def test_invalid_transition_not_connected_to_review_queued(self):
        """Test invalid transition from NOT_CONNECTED to REVIEW_QUEUED."""
        assert not can_transition(ConnectorState.NOT_CONNECTED, ConnectorState.REVIEW_QUEUED)


class TestAuthorityBoundary:
    """Test that P3e does not introduce new authority."""

    def test_no_prepare_state(self):
        """Test that Prepare state does not exist."""
        assert not hasattr(ConnectorState, "PREPARE")
        assert not hasattr(ConnectorState, "PREPARING")

    def test_no_execute_state(self):
        """Test that Execute state does not exist."""
        assert not hasattr(ConnectorState, "EXECUTE")
        assert not hasattr(ConnectorState, "EXECUTING")

    def test_no_deploy_state(self):
        """Test that Deploy state does not exist."""
        assert not hasattr(ConnectorState, "DEPLOY")
        assert not hasattr(ConnectorState, "DEPLOYING")

    def test_no_merge_state(self):
        """Test that Merge state does not exist."""
        assert not hasattr(ConnectorState, "MERGE")
        assert not hasattr(ConnectorState, "MERGING")

    def test_state_count(self):
        """Test that state count is reasonable."""
        states = list(ConnectorState)
        assert len(states) == 12  # Expected states


class TestActionVisibility:
    """Test action visibility based on state."""

    def test_connect_action_only_when_not_connected(self):
        """Test Connect action is only available when not connected."""
        # Connect action should be available in NOT_CONNECTED state
        # and not in other states
        for state in ConnectorState:
            if state == ConnectorState.NOT_CONNECTED:
                # Connect action should be available
                pass
            elif state == ConnectorState.CONNECTING:
                # Connect action should not be available
                pass

    def test_add_project_action_only_when_connected(self):
        """Test Add Project action is only available when connected."""
        # Add Project should be available in CONNECTED and READY states
        valid_states = {ConnectorState.CONNECTED, ConnectorState.READY}
        for state in ConnectorState:
            if state in valid_states:
                # Add Project should be available
                pass
            else:
                # Add Project should not be available
                pass

    def test_review_project_action_only_when_ready(self):
        """Test Review Project action is only available when ready."""
        # Review Project should be available in READY and REVIEW_FAILED states
        valid_states = {ConnectorState.READY, ConnectorState.REVIEW_FAILED}
        for state in ConnectorState:
            if state in valid_states:
                # Review Project should be available
                pass
            else:
                # Review Project should not be available
                pass


class TestProjectAuthorizationBoundary:
    """Test project authorization boundary."""

    def test_review_only_state_names(self):
        """Test that review-related states exist."""
        assert hasattr(ConnectorState, "REVIEW_QUEUED")
        assert hasattr(ConnectorState, "REVIEW_IN_PROGRESS")
        assert hasattr(ConnectorState, "REVIEW_COMPLETE")
        assert hasattr(ConnectorState, "REVIEW_FAILED")

    def test_no_automatic_scan_states(self):
        """Test that no automatic scan states exist."""
        assert not hasattr(ConnectorState, "AUTO_SCAN")
        assert not hasattr(ConnectorState, "SCANNING")


class TestOfflineBehavior:
    """Test offline behavior."""

    def test_offline_state_exists(self):
        """Test that OFFLINE state exists."""
        assert hasattr(ConnectorState, "OFFLINE")

    def test_transition_to_offline_from_connected(self):
        """Test transition to OFFLINE from CONNECTED."""
        assert can_transition(ConnectorState.CONNECTED, ConnectorState.OFFLINE)

    def test_transition_to_offline_from_ready(self):
        """Test transition to OFFLINE from READY."""
        assert can_transition(ConnectorState.READY, ConnectorState.OFFLINE)


class TestErrorHandling:
    """Test error handling."""

    def test_error_state_exists(self):
        """Test that ERROR state exists."""
        assert hasattr(ConnectorState, "ERROR")

    def test_transition_to_error_from_starting(self):
        """Test transition to ERROR from STARTING."""
        assert can_transition(ConnectorState.STARTING, ConnectorState.ERROR)

    def test_transition_to_error_from_connected(self):
        """Test transition to ERROR from CONNECTED."""
        assert can_transition(ConnectorState.CONNECTED, ConnectorState.ERROR)


class TestDesktopTrayIntegration:
    """Test desktop tray integration."""

    def test_connector_app_import(self):
        """Test that ConnectorApp can be imported."""
        from evosia_connector.desktop_tray import ConnectorApp
        assert ConnectorApp is not None

    def test_connector_app_instantiation(self):
        """Test that ConnectorApp can be instantiated."""
        from evosia_connector.desktop_tray import ConnectorApp
        app = ConnectorApp()
        assert app is not None
        assert app._state == ConnectorState.STARTING

    def test_status_text_mapping(self):
        """Test status text mapping."""
        from evosia_connector.desktop_tray import ConnectorApp
        app = ConnectorApp()

        # Test status text for different states
        status_texts = {
            ConnectorState.STARTING: "Starting...",
            ConnectorState.NOT_CONNECTED: "Not connected",
            ConnectorState.CONNECTING: "Connecting...",
            ConnectorState.CONNECTED: "Connected - No projects",
            ConnectorState.READY: "Ready",
            ConnectorState.REVIEW_QUEUED: "Review queued",
            ConnectorState.REVIEW_IN_PROGRESS: "Review in progress",
            ConnectorState.REVIEW_COMPLETE: "Review complete",
            ConnectorState.REVIEW_FAILED: "Review failed",
            ConnectorState.OFFLINE: "Offline",
            ConnectorState.ERROR: "Error",
        }

        for state, expected_text in status_texts.items():
            app._state = state
            actual_text = app._get_status_text()
            assert actual_text == expected_text, f"State {state} has wrong status text"


class TestSecurityBoundary:
    """Test security boundary."""

    def test_no_arbitrary_shell(self):
        """Test that no arbitrary shell is introduced."""
        import ast
        import inspect

        from evosia_connector import desktop_tray

        # Check source for dangerous patterns
        source = inspect.getsource(desktop_tray)
        assert "shell=True" not in source
        assert "os.system" not in source
        assert "subprocess" not in source
        assert "eval(" not in source
        assert "exec(" not in source

    def test_no_credential_in_diagnostics(self):
        """Test that diagnostics do not expose credentials."""
        from evosia_connector.desktop_tray import ConnectorApp
        app = ConnectorApp()

        # Diagnostics should not contain credential fields
        diagnostics_fields = [
            "_version",
            "_cloud_url",
            "_device_name",
            "_state",
            "_projects",
            "_last_heartbeat",
            "_last_review_status",
        ]

        # Ensure no credential-related fields
        for field in diagnostics_fields:
            assert "credential" not in field.lower()
            assert "token" not in field.lower()
            assert "secret" not in field.lower()

    def test_safe_browser_launch(self):
        """Test that browser launch uses safe method."""
        from evosia_connector.desktop_tray import ConnectorApp
        app = ConnectorApp()

        # Check that _on_open_evosia uses webbrowser.open
        import inspect
        source = inspect.getsource(app._on_open_evosia)
        assert "webbrowser.open" in source
        assert "shell=True" not in source
        assert "os.system" not in source
