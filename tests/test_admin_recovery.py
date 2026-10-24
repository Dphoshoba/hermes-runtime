"""Owner recovery is tested only against isolated, disposable databases."""

from __future__ import annotations

import getpass
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from enterprise import admin
from enterprise.database import Base
from enterprise.models import (
    BootstrapToken,
    Device,
    DeviceProject,
    JournalEvent,
    PairingRequest,
    ProjectAuthorizationRequest,
    ProjectAuthorizationToken,
    Repository,
    User,
    UserWorkspace,
    Workspace,
)
from enterprise.routers import login
from enterprise.schemas import UserLogin
from enterprise.services import (
    create_access_token,
    get_current_user,
    hash_password,
    pwd_context,
    verify_password,
)
from evosia.journal_models import _canonical_payload_sha256

OLD = "Old-test-password-479!"
NEW = "New-test-password-851!"
EMAIL = "owner@example.com"


def snapshot(engine):
    with engine.connect() as conn:
        return {
            table.name: sorted(
                [dict(row) for row in conn.execute(select(table)).mappings()],
                key=lambda row: str(row["id"]),
            )
            for table in Base.metadata.sorted_tables
        }


@pytest.fixture
def recovery(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(admin, "SessionLocal", factory)
    with factory.begin() as db:
        db.add_all(
            [
                User(
                    id="owner",
                    email=EMAIL,
                    name="Owner",
                    is_admin=True,
                    hashed_password=hash_password(OLD),
                ),
                User(
                    id="other",
                    email="other@example.com",
                    name="Other",
                    hashed_password=hash_password(OLD),
                ),
                Workspace(id="workspace", name="Workspace", slug="workspace"),
                Repository(id="repository", name="Repository", url="local-test-only"),
            ]
        )
        db.flush()
        db.add_all(
            [
                UserWorkspace(
                    id="membership",
                    user_id="other",
                    workspace_id="workspace",
                    role="admin",
                ),
                Device(
                    id="device",
                    device_id="device-key",
                    user_id="owner",
                    device_name="Test",
                    platform="windows",
                    agent_version="1",
                    status="active",
                ),
                JournalEvent(
                    id="existing-event",
                    event_id="existing-event",
                    timestamp="2026-01-01",
                    event_type="existing",
                    stage="test",
                    payload={},
                    payload_sha256="existing",
                ),
            ]
        )
        db.flush()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.add_all(
            [
                DeviceProject(
                    id="project",
                    device_id="device-key",
                    user_id="owner",
                    display_name="Project",
                ),
                BootstrapToken(
                    id="bootstrap",
                    token_hash="test-bootstrap-hash",
                    device_id="device-key",
                    user_id="owner",
                    expires_at=expiry,
                ),
                ProjectAuthorizationToken(
                    id="authorization",
                    token_hash="test-authorization-hash",
                    device_id="device-key",
                    user_id="owner",
                    expires_at=expiry,
                ),
                PairingRequest(
                    id="pairing",
                    pairing_id="test-pairing-request",
                    user_id="owner",
                    device_name="Test pairing",
                    platform="windows",
                    agent_version="1",
                    status="APPROVED",
                    expires_at=expiry,
                ),
                ProjectAuthorizationRequest(
                    id="project-request",
                    request_id="test-project-request",
                    device_id="device-key",
                    user_id="owner",
                    display_name="Test authorization",
                    local_root_fingerprint="test-local-root-fingerprint",
                    platform="windows",
                    agent_version="1",
                    status="APPROVED",
                    expires_at=expiry,
                ),
            ]
        )
    prompts = Mock(side_effect=[NEW, NEW])
    monkeypatch.setattr(admin.getpass, "getpass", prompts)
    confirmation = Mock(return_value="RESET")
    monkeypatch.setattr("builtins.input", confirmation)
    yield engine, factory, prompts, confirmation
    engine.dispose()


def run(email=EMAIL):
    return admin.main(["reset-owner-password", "--email", email])


def assert_sanitized(capsys, caplog, *secrets):
    output = capsys.readouterr()
    text = output.out + output.err + caplog.text
    for secret in (NEW, OLD, *secrets):
        assert secret not in text


def test_reset_normal_login_and_preserve_all_other_records(recovery, capsys, caplog):
    engine, factory, prompts, confirmation = recovery
    before = snapshot(engine)
    with factory() as db:
        token = create_access_token({"sub": "owner"})
        old_hash = db.get(User, "owner").hashed_password
    assert run("  OWNER@EXAMPLE.COM  ") == 0
    prompts.assert_any_call("New password: ")
    assert prompts.call_count == 2
    confirmation.assert_called_once()
    with factory() as db:
        owner = db.get(User, "owner")
        new_hash = owner.hashed_password
        assert pwd_context.identify(new_hash) == "bcrypt"
        assert pwd_context.handler("bcrypt").from_string(new_hash).rounds == 12
        assert verify_password(NEW, new_hash)
        assert not verify_password(OLD, new_hash)
        assert login(UserLogin(email=EMAIL, password=NEW), db).access_token
        with pytest.raises(HTTPException) as exc:
            login(UserLogin(email=EMAIL, password=OLD), db)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid credentials"
        assert get_current_user(token, db).id == "owner"
        audit = (
            db.query(JournalEvent)
            .filter_by(event_type="security.owner_password_reset")
            .one()
        )
        assert audit.payload == {"user_id": "owner", "method": "admin_cli"}
        assert audit.payload_sha256 == _canonical_payload_sha256(audit.payload)
        assert audit.actor == "admin_cli"
        assert audit.repository_id is None
    after = snapshot(engine)
    after["users"] = [
        {**row, "hashed_password": old_hash} if row["id"] == "owner" else row
        for row in after["users"]
    ]
    after["journal_events"] = [
        row for row in after["journal_events"] if row["id"] == "existing-event"
    ]
    assert after == before
    assert_sanitized(capsys, caplog, old_hash, new_hash)


@pytest.mark.parametrize(
    "email", ["missing@example.com", "other@example.com", "not-an-email"]
)
def test_ineligible_lookup_does_not_write(recovery, email, capsys, caplog):
    engine, _, prompts, confirmation = recovery
    before = snapshot(engine)
    assert run(email) != 0
    assert snapshot(engine) == before
    prompts.assert_not_called()
    confirmation.assert_not_called()
    assert_sanitized(capsys, caplog)


def test_ambiguous_normalized_email_does_not_write(recovery, capsys, caplog):
    engine, factory, prompts, _ = recovery
    with factory.begin() as db:
        db.add(
            User(
                email=" OWNER@example.com ",
                name="Duplicate",
                is_admin=True,
                hashed_password=hash_password(OLD),
            )
        )
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    prompts.assert_not_called()
    assert_sanitized(capsys, caplog)


def test_inactive_admin_does_not_write(recovery):
    engine, factory, prompts, _ = recovery
    with factory.begin() as db:
        db.get(User, "owner").is_active = False
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    prompts.assert_not_called()


@pytest.mark.parametrize(
    "first,second",
    [
        (NEW, "different-secret"),
        ("short", "short"),
        ("x" * 129, "x" * 129),
        ("x" * 73, "x" * 73),
        ("\u00e9" * 37, "\u00e9" * 37),
    ],
)
def test_invalid_password_does_not_write(recovery, first, second, capsys, caplog):
    engine, _, prompts, confirmation = recovery
    prompts.side_effect = [first, second]
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    confirmation.assert_not_called()
    assert_sanitized(capsys, caplog, first, second)


@pytest.mark.parametrize("answer", ["", "reset", "no", "RESET "])
def test_declined_confirmation_does_not_write(recovery, answer, capsys, caplog):
    engine, _, _, confirmation = recovery
    confirmation.return_value = answer
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    assert_sanitized(capsys, caplog)


@pytest.mark.parametrize("failure_stage", ["lookup", "update", "audit", "commit"])
def test_database_failure_rolls_back_everything(
    recovery, failure_stage, capsys, caplog
):
    engine, _, _, _ = recovery
    before = snapshot(engine)
    observed = []

    def fail_statement(conn, cursor, statement, parameters, context, executemany):
        observed.append(statement)
        should_fail = (
            (failure_stage == "lookup" and statement.startswith("SELECT"))
            or (failure_stage == "update" and statement.startswith("UPDATE"))
            or (
                failure_stage == "audit"
                and statement.startswith("INSERT INTO journal_events")
            )
        )
        if should_fail:
            raise SQLAlchemyError(f"Do not print SQL parameters: {NEW}")

    def fail_commit(conn):
        if failure_stage == "commit":
            raise SQLAlchemyError(f"Do not print exception data: {NEW}")

    event.listen(engine, "before_cursor_execute", fail_statement)
    event.listen(engine, "commit", fail_commit)
    try:
        assert run() != 0
    finally:
        event.remove(engine, "before_cursor_execute", fail_statement)
        event.remove(engine, "commit", fail_commit)
    assert snapshot(engine) == before
    if failure_stage in ("audit", "commit"):
        assert any(statement.startswith("UPDATE users") for statement in observed)
    assert_sanitized(capsys, caplog)


@pytest.mark.parametrize("failure", [EOFError, KeyboardInterrupt, OSError])
def test_input_failure_is_sanitized_and_no_write(recovery, failure, capsys, caplog):
    engine, _, prompts, _ = recovery
    before = snapshot(engine)
    prompts.side_effect = failure(NEW)
    assert run() != 0
    assert snapshot(engine) == before
    assert_sanitized(capsys, caplog)


def test_getpass_echo_fallback_is_forbidden(recovery, monkeypatch):
    engine, _, _, _ = recovery
    before = snapshot(engine)

    def insecure_prompt(prompt):
        warnings.warn("Cannot disable echo", getpass.GetPassWarning)
        pytest.fail("Must abort before insecure fallback reads a password")

    monkeypatch.setattr(admin.getpass, "getpass", insecure_prompt)
    assert run() != 0
    assert snapshot(engine) == before


def test_hashing_failure_is_sanitized(recovery, monkeypatch, capsys, caplog):
    engine, _, _, _ = recovery
    before = snapshot(engine)
    monkeypatch.setattr(admin, "hash_password", Mock(side_effect=ValueError(NEW)))
    assert run() != 0
    assert snapshot(engine) == before
    assert_sanitized(capsys, caplog)


def test_concurrent_account_change_fails_closed(recovery):
    engine, _, _, confirmation = recovery

    def change_role(prompt):
        with engine.begin() as conn:
            conn.execute(
                User.__table__.update().where(User.id == "owner").values(is_admin=False)
            )
        return "RESET"

    confirmation.side_effect = change_role
    before = snapshot(engine)
    assert run() != 0
    after = snapshot(engine)
    assert before["users"][1]["hashed_password"] == after["users"][1]["hashed_password"]
    assert before["journal_events"] == after["journal_events"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["reset-owner-password"],
        ["reset-owner-password", "--email", EMAIL, "--password", NEW],
        ["reset-owner-password", "--email", EMAIL, NEW],
        [NEW],
        [],
    ],
)
def test_invalid_cli_never_connects_or_echoes_arguments(
    monkeypatch, arguments, capsys, caplog
):
    factory = Mock(side_effect=AssertionError("Must not connect"))
    monkeypatch.setattr(admin, "SessionLocal", factory)
    with pytest.raises(SystemExit) as exc:
        admin.main(arguments)
    assert exc.value.code != 0
    factory.assert_not_called()
    assert_sanitized(capsys, caplog)


def test_no_reset_http_surface_or_auth_bypass(recovery):
    from enterprise.app import app

    paths = app.openapi()["paths"]
    auth_routes = {
        (path, method.upper())
        for path, methods in paths.items()
        if path.startswith("/api/auth")
        for method in methods
    }
    assert auth_routes == {
        ("/api/auth/register", "POST"),
        ("/api/auth/login", "POST"),
        ("/api/auth/me", "GET"),
    }
    assert not any(
        "password" in path.lower() or "reset" in path.lower() for path in paths
    )
    _, factory, _, _ = recovery
    with factory() as db:
        assert login(UserLogin(email=EMAIL, password=OLD), db).access_token
        with pytest.raises(HTTPException) as exc:
            login(UserLogin(email=EMAIL, password=NEW), db)
        assert exc.value.status_code == 401
        with pytest.raises(HTTPException) as exc:
            get_current_user("not-a-jwt", db)
        assert exc.value.status_code == 401
