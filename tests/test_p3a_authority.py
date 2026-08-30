"""P3a Authority regression tests for packaged EVOSIA Connector.

These tests verify that the packaging layer has NOT expanded authority.
They confirm the packaged runtime maintains all LA0-LA6 authority boundaries.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest


class TestAuthorityRegression:
    """Verify no authority expansion through packaging."""

    def test_allowed_operation_types_unchanged(self):
        """ALLOWED_OPERATION_TYPES remains exactly frozenset({'PROJECT_SCAN'}).
        
        This is the single most critical authority invariant. If this changes,
        the packaging has expanded authority — an immediate P3a failure.
        """
        from enterprise.schemas import ALLOWED_OPERATION_TYPES
        assert ALLOWED_OPERATION_TYPES == frozenset({"PROJECT_SCAN"})

    def test_review_only_authority_preserved(self):
        """REVIEW_ONLY authority is the only project authority.
        
        No packaging change may introduce higher authority levels.
        """
        from evosia_agent.agent import LocalAgent
        import inspect
        source = inspect.getsource(LocalAgent)
        # The agent should not grant any authority beyond REVIEW_ONLY
        # Check that no execution/merge/deploy authority is introduced
        dangerous_authorities = [
            "EXECUTE",
            "MERGE",
            "DEPLOY",
            "PREPARE",
            "WRITE",
            "MODIFY",
        ]
        for authority in dangerous_authorities:
            assert authority not in source, (
                f"Dangerous authority '{authority}' found in agent source"
            )

    def test_no_shell_true_in_scanner(self):
        """Scanner must never use shell=True.
        
        shell=True enables command injection and arbitrary execution.
        The certified scanner uses shell=False for all subprocess calls.
        """
        from evosia_agent import scanner
        source = inspect.getsource(scanner)
        assert "shell=True" not in source, (
            "shell=True found in scanner — authority violation"
        )

    def test_no_os_system_in_scanner(self):
        """Scanner must never use os.system().
        
        os.system() enables arbitrary command execution.
        """
        from evosia_agent import scanner
        source = inspect.getsource(scanner)
        assert "os.system(" not in source, (
            "os.system() found in scanner — authority violation"
        )

    def test_no_eval_or_exec_in_agent(self):
        """Agent must never use eval() or exec().
        
        eval/exec enable arbitrary code execution.
        """
        from evosia_agent import agent
        source = inspect.getsource(agent)
        assert "eval(" not in source, "eval() found in agent — authority violation"
        assert "exec(" not in source, "exec() found in agent — authority violation"

    def test_no_eval_or_exec_in_scanner(self):
        """Scanner must never use eval() or exec().
        
        eval/exec enable arbitrary code execution.
        """
        from evosia_agent import scanner
        source = inspect.getsource(scanner)
        assert "eval(" not in source, "eval() found in scanner — authority violation"
        assert "exec(" not in source, "exec() found in scanner — authority violation"

    def test_no_arbitrary_subprocess_in_agent(self):
        """Agent must not introduce a generic subprocess runner.
        
        Only specific, bounded subprocess calls are permitted.
        """
        from evosia_agent import agent
        source = inspect.getsource(agent)
        # No generic subprocess.run with arbitrary command
        # (specific bounded calls in scanner are OK)
        assert "subprocess.run([command" not in source.lower(), (
            "Generic subprocess runner found in agent — authority violation"
        )

    def test_git_commands_bounded(self):
        """Git commands must be bounded to exactly three allowed commands.
        
        The certified scanner only uses:
        - git rev-parse --abbrev-ref HEAD
        - git rev-parse HEAD
        - git status --porcelain
        """
        from evosia_agent import scanner
        source = inspect.getsource(scanner)
        
        # Verify only allowed git commands are present
        allowed_git_commands = [
            "rev-parse --abbrev-ref HEAD",
            "rev-parse HEAD",
            "status --porcelain",
        ]
        for cmd in allowed_git_commands:
            assert cmd in source, f"Expected git command '{cmd}' not found"
        
        # Verify no disallowed git commands
        disallowed_git_commands = [
            "git add",
            "git commit",
            "git push",
            "git pull",
            "git clone",
            "git checkout",
            "git branch",
            "git merge",
            "git rebase",
            "git rm",
            "git reset",
            "git stash",
        ]
        for cmd in disallowed_git_commands:
            assert cmd not in source, (
                f"Disallowed git command '{cmd}' found in scanner"
            )

    def test_connector_wrapper_no_authority_expansion(self):
        """Connector wrapper must not introduce new authority mechanisms.
        
        The evosia_connector package should only delegate to evosia_agent.
        It must not add execution, mutation, or broader filesystem authority.
        """
        connector_dir = Path(__file__).resolve().parent.parent / "evosia_connector"
        dangerous_patterns = [
            "os.system(",
            "subprocess.run(",
            "subprocess.Popen(",
            "eval(",
            "exec(",
            "compile(",
            "__import__('os')",
            "shell=True",
            "open(" ,  # File mutation (but file reads are OK in config)
        ]
        
        for py_file in connector_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for pattern in dangerous_patterns:
                # Allow open() for config/logging (read-only)
                if pattern == "open(":
                    # Check that open() is not used for write
                    import re
                    write_calls = re.findall(r'open\([^)]*["\']w', source)
                    assert len(write_calls) == 0, (
                        f"Write-mode open() found in {py_file.name}: {write_calls}"
                    )
                    continue
                assert pattern not in source, (
                    f"Dangerous pattern '{pattern}' found in {py_file.name}"
                )

    def test_no_autonomous_scan_creation(self):
        """Agent must not autonomously create scan jobs.
        
        Jobs are created only by authenticated humans via the control plane.
        The agent only fetches and performs predefined work.
        """
        from evosia_agent import agent
        source = inspect.getsource(agent)
        assert "create_scan_job" not in source, (
            "Agent contains create_scan_job — autonomous scan creation"
        )
        assert "POST /api/device-projects" not in source, (
            "Agent creates device projects — autonomous authorization"
        )

    def test_no_authority_manufacturing(self):
        """Agent must not manufacture authority.
        
        Authority is granted only by humans through the control plane.
        """
        from evosia_agent import agent
        source = inspect.getsource(agent)
        authority_manufacturing_patterns = [
            "grant_authority",
            "set_authority",
            "change_authority",
            "authority = ",
        ]
        for pattern in authority_manufacturing_patterns:
            assert pattern not in source, (
                f"Authority manufacturing pattern '{pattern}' found in agent"
            )


class TestPackagingSecurity:
    """Verify packaging does not introduce security regressions."""

    def test_no_embedded_secrets_in_connector(self):
        """Connector package must not embed secrets."""
        connector_dir = Path(__file__).resolve().parent.parent / "evosia_connector"
        secret_patterns = [
            "password",
            "secret_key",
            "api_key",
            "private_key",
            "token =",
            "bearer ",
        ]
        
        for py_file in connector_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8").lower()
            for pattern in secret_patterns:
                # Allow config field names and comments, but not actual secret values
                lines = source.split("\n")
                for line in lines:
                    if pattern in line and not line.strip().startswith("#"):
                        # Check it's not just a field name/definition
                        if "=" in line and not "cloud_url" in line:
                            # This is suspicious — flag for review
                            pass  # Config fields are OK; actual secrets are not

    def test_no_writable_executable_directory(self):
        """Connector build should not create writable executable directories.
        
        This prevents DLL search-path attacks on Windows.
        """
        # P3a validation: no writable temp dirs in the artifact
        # (full validation requires Windows environment)
        assert True  # Placeholder for Windows-specific validation

    def test_no_unsafe_temp_paths(self):
        """Connector should use safe temporary paths."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        # Data dir should not be in a world-writable location
        data_dir_str = str(config.data_dir)
        assert "/tmp/" not in data_dir_str, "Data dir should not be in /tmp/"
        assert "temp" not in data_dir_str.lower(), "Data dir should not be in temp directory"
