"""First-owner bootstrap against synthetic, disposable databases only."""

from __future__ import annotations

import ast
import getpass
import inspect
import multiprocessing
import os
import threading
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from test_admin_recovery import NEW, assert_sanitized, recovery, snapshot  # noqa: F401

from enterprise import admin
from enterprise.database import Base
from enterprise.models import JournalEvent, User
from enterprise.services import pwd_context, verify_password
from evosia.journal_models import _canonical_payload_sha256

EMAIL = "first-owner@example.com"
PARTICIPANT = "m8-participant@example.com"


@pytest.fixture
def bootstrap(recovery):  # noqa: F811 - imported pytest fixture
    engine, factory, prompts, confirmation = recovery
    with factory.begin() as db:
        participant = db.get(User, "owner")
        participant.is_admin = False
        participant.email = PARTICIPANT
        participant.name = "M8 Participant"
    confirmation.return_value = "BOOTSTRAP"
    return engine, factory, prompts, confirmation


@pytest.fixture
def session_attempts(bootstrap, monkeypatch):
    _, factory, _, _ = bootstrap
    attempts = Mock(wraps=factory)
    monkeypatch.setattr(admin, "SessionLocal", attempts)
    return attempts


def run(email=EMAIL):
    return admin.main(["bootstrap-first-owner", "--email", email])


def test_create_one_owner_and_preserve_every_existing_record(
    bootstrap, capsys, caplog, monkeypatch
):
    engine, factory, prompts, confirmation = bootstrap
    before = snapshot(engine)
    # A bootstrap must not issue a token, including via a future helper.
    monkeypatch.setattr(
        "enterprise.services.create_access_token",
        Mock(side_effect=AssertionError("Bootstrap must not issue a JWT")),
    )
    assert run("  FIRST-OWNER@EXAMPLE.COM  ") == 0
    with factory() as db:
        owner = db.query(User).filter_by(is_admin=True).one()
        assert owner.email == EMAIL
        assert owner.is_active is True
        assert uuid.UUID(owner.id).version == 4
        assert owner.created_at is not None and owner.updated_at is not None
        hashed = owner.hashed_password
        assert verify_password(NEW, hashed)
        assert pwd_context.identify(hashed) == "bcrypt"
        assert pwd_context.handler("bcrypt").from_string(hashed).rounds == 12
        audit = (
            db.query(JournalEvent)
            .filter_by(event_type="security.first_owner_bootstrapped")
            .one()
        )
        assert audit.payload == {"user_id": owner.id, "method": "admin_cli"}
        assert audit.payload_sha256 == _canonical_payload_sha256(audit.payload)
        assert audit.actor == "admin_cli"
        assert audit.repository_id is None
        assert len(audit.timestamp) <= 30
        new_id, event_id = owner.id, audit.id
    after = snapshot(engine)
    assert len(after["users"]) == len(before["users"]) + 1
    assert len(after["journal_events"]) == len(before["journal_events"]) + 1
    after["users"] = [row for row in after["users"] if row["id"] != new_id]
    after["journal_events"] = [
        row for row in after["journal_events"] if row["id"] != event_id
    ]
    assert after == before
    assert prompts.call_count == 2
    confirmation.assert_called_once_with("Type BOOTSTRAP to create the first owner: ")
    assert_sanitized(capsys, caplog, hashed)


@pytest.mark.parametrize("active", [True, False])
def test_any_existing_global_admin_blocks(bootstrap, active, capsys, caplog):
    engine, factory, prompts, _ = bootstrap
    with factory.begin() as db:
        other = db.get(User, "other")
        other.is_admin = True
        other.is_active = active
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    assert prompts.call_count == 2
    assert_sanitized(capsys, caplog)


@pytest.mark.parametrize("email", ["other@example.com", "  OTHER@EXAMPLE.COM  "])
def test_existing_normalized_email_blocks(bootstrap, email):
    engine, _, prompts, _ = bootstrap
    before = snapshot(engine)
    assert run(email) != 0
    assert snapshot(engine) == before
    assert prompts.call_count == 2


@pytest.mark.parametrize("exists", [True, False])
def test_fixture_address_is_never_created_or_modified(
    bootstrap, session_attempts, exists
):
    engine, factory, prompts, _ = bootstrap
    if not exists:
        with factory.begin() as db:
            db.get(User, "owner").email = "renamed-fixture@example.com"
    before = snapshot(engine)
    assert run("  M8-PARTICIPANT@EXAMPLE.COM  ") != 0
    assert snapshot(engine) == before
    prompts.assert_not_called()
    session_attempts.assert_not_called()


@pytest.mark.parametrize(
    "first,second",
    [
        (NEW, "mismatched-secret"),
        ("short", "short"),
        ("x" * 129, "x" * 129),
        ("x" * 73, "x" * 73),
        ("\u00e9" * 37, "\u00e9" * 37),
    ],
)
def test_password_failure_leaves_no_writes(
    bootstrap, session_attempts, first, second, capsys, caplog
):
    engine, _, prompts, confirmation = bootstrap
    prompts.side_effect = [first, second]
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    confirmation.assert_not_called()
    session_attempts.assert_not_called()
    assert_sanitized(capsys, caplog, first, second)


@pytest.mark.parametrize("answer", ["", "bootstrap", "RESET", "BOOTSTRAP "])
def test_confirmation_must_be_exact(
    bootstrap, session_attempts, answer, capsys, caplog
):
    engine, _, _, confirmation = bootstrap
    confirmation.return_value = answer
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    session_attempts.assert_not_called()
    assert_sanitized(capsys, caplog)


@pytest.mark.parametrize("stage", ["lookup", "user", "journal", "commit"])
def test_database_failure_rolls_back_user_and_event(bootstrap, stage, capsys, caplog):
    engine, _, _, _ = bootstrap
    before = snapshot(engine)
    statements = []

    def fail(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if (
            (stage == "lookup" and statement.startswith("SELECT"))
            or (stage == "user" and statement.startswith("INSERT INTO users"))
            or (
                stage == "journal"
                and statement.startswith("INSERT INTO journal_events")
            )
        ):
            raise SQLAlchemyError(NEW)

    def fail_commit(conn):
        if stage == "commit":
            raise SQLAlchemyError(NEW)

    event.listen(engine, "before_cursor_execute", fail)
    event.listen(engine, "commit", fail_commit)
    try:
        assert run() != 0
    finally:
        event.remove(engine, "before_cursor_execute", fail)
        event.remove(engine, "commit", fail_commit)
    assert snapshot(engine) == before
    if stage == "user":
        assert not any(s.startswith("INSERT INTO journal_events") for s in statements)
    if stage in ("journal", "commit"):
        assert any(s.startswith("INSERT INTO users") for s in statements)
    assert_sanitized(capsys, caplog)


def test_second_invocation_is_blocked_after_password_confirmation(bootstrap):
    engine, _, prompts, _ = bootstrap
    assert run() == 0
    before = snapshot(engine)
    prompts.reset_mock()
    prompts.side_effect = [NEW, NEW]
    assert run("second-owner@example.com") != 0
    assert prompts.call_count == 2
    assert snapshot(engine) == before


@pytest.mark.parametrize("stage", ["first", "repeat", "confirmation"])
@pytest.mark.parametrize("failure", [EOFError, KeyboardInterrupt, OSError, ValueError])
def test_input_errors_are_sanitized_without_opening_a_session(
    bootstrap, session_attempts, stage, failure, capsys, caplog
):
    engine, _, prompts, confirmation = bootstrap
    if stage == "confirmation":
        confirmation.side_effect = failure(NEW)
    else:
        prompts.side_effect = [NEW, failure(NEW)] if stage == "repeat" else failure(NEW)
    before = snapshot(engine)
    assert run() != 0
    assert snapshot(engine) == before
    session_attempts.assert_not_called()
    assert_sanitized(capsys, caplog)


def test_insecure_echo_is_forbidden(bootstrap, session_attempts, monkeypatch):
    engine, _, _, _ = bootstrap
    before = snapshot(engine)

    def insecure(prompt):
        warnings.warn("Cannot disable echo", getpass.GetPassWarning)
        pytest.fail("Must stop before reading an unmasked password")

    monkeypatch.setattr(admin.getpass, "getpass", insecure)
    assert run() != 0
    assert snapshot(engine) == before
    session_attempts.assert_not_called()


def test_hash_failure_is_sanitized_without_any_write(
    bootstrap, session_attempts, monkeypatch, capsys, caplog
):
    engine, _, _, _ = bootstrap
    before = snapshot(engine)
    monkeypatch.setattr(admin, "hash_password", Mock(side_effect=ValueError(NEW)))
    assert run() != 0
    assert snapshot(engine) == before
    session_attempts.assert_not_called()
    assert_sanitized(capsys, caplog)


@pytest.mark.parametrize(
    "arguments",
    [
        ["bootstrap-first-owner"],
        ["bootstrap-first-owner", "--email", EMAIL, "--password", NEW],
        ["bootstrap-first-owner", "--email", EMAIL, NEW],
        ["bootstrap-first-owner", "--email", EMAIL, "--confirmation", "BOOTSTRAP"],
    ],
)
def test_cli_rejects_secret_arguments_without_echo(
    monkeypatch, arguments, capsys, caplog
):
    factory = Mock(side_effect=AssertionError("Must not connect"))
    monkeypatch.setattr(admin, "SessionLocal", factory)
    with pytest.raises(SystemExit) as exc:
        admin.main(arguments)
    assert exc.value.code != 0
    factory.assert_not_called()
    assert_sanitized(capsys, caplog)


def test_invalid_email_never_connects(monkeypatch):
    factory = Mock(side_effect=AssertionError("Must not connect"))
    monkeypatch.setattr(admin, "SessionLocal", factory)
    assert run("invalid-email") != 0
    factory.assert_not_called()


def test_unsupported_database_fails_closed(bootstrap, monkeypatch):
    engine, _, prompts, _ = bootstrap
    before = snapshot(engine)
    with monkeypatch.context() as patch:
        patch.setattr(engine.dialect, "name", "unsupported")
        assert run() != 0
    assert snapshot(engine) == before
    assert prompts.call_count == 2


def test_prompts_confirmation_and_hash_finish_before_any_database_access(
    bootstrap, session_attempts, monkeypatch
):
    engine, _, prompts, confirmation = bootstrap
    stages = []
    original_hash = admin.hash_password

    def assert_no_database_access():
        session_attempts.assert_not_called()

    def password_prompt(prompt):
        assert_no_database_access()
        stages.append("password")
        return NEW

    def confirm(prompt):
        assert_no_database_access()
        assert stages == ["password", "password"]
        stages.append("confirmation")
        return "BOOTSTRAP"

    def hash_after_confirmation(password):
        assert_no_database_access()
        assert stages == ["password", "password", "confirmation"]
        result = original_hash(password)
        assert_no_database_access()
        stages.append("hash")
        return result

    def observe(conn, cursor, statement, parameters, context, executemany):
        assert stages[:4] == ["password", "password", "confirmation", "hash"]
        if statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE")):
            stages.append("lock")
        elif statement.startswith("INSERT"):
            assert "lock" in stages

    prompts.side_effect = password_prompt
    confirmation.side_effect = confirm
    monkeypatch.setattr(admin, "hash_password", hash_after_confirmation)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        assert run() == 0
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    session_attempts.assert_called_once_with()
    assert stages == ["password", "password", "confirmation", "hash", "lock"]


def test_reset_implementation_and_public_surface_are_unchanged():
    from enterprise.app import app

    paths = app.openapi()["paths"]
    assert not any(
        any(term in path.lower() for term in ("bootstrap", "password", "reset"))
        for path in paths
    )
    # The reference is a committed source fingerprint, not an input snapshot.
    import hashlib

    source = inspect.getsource(admin._reset_owner_password)
    assert hashlib.sha256(source.encode()).hexdigest() == RESET_SOURCE_SHA256
    tree = ast.parse(Path(admin.__file__).read_text(encoding="utf-8"))
    bootstrap_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_bootstrap_first_owner"
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "create_access_token"
        for node in ast.walk(bootstrap_node)
    )


RESET_SOURCE_SHA256 = "316b5ffb65deec4d9851286f2161d1b462fc125ef76004b0a5c7c11df82e773d"


@pytest.fixture(params=["sqlite", "postgresql", "postgresql-repeatable-read"])
def concurrent_database(request, tmp_path):
    if request.param == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'bootstrap.db'}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )
    else:
        if os.environ.get("EVOSIA_TEST_LOCAL_POSTGRES") != "1":
            pytest.skip("Requires explicitly enabled disposable loopback PostgreSQL")
        # Never accept an arbitrary DB URL from the environment.
        engine = create_engine(
            "postgresql+psycopg://bootstrap_test@127.0.0.1:55483/bootstrap_test",
            isolation_level=(
                "REPEATABLE READ"
                if request.param.endswith("repeatable-read")
                else "READ COMMITTED"
            ),
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.parametrize("competitor", ["active-admin", "inactive-admin", "email"])
def test_competing_record_after_input_is_rejected_under_lock(
    concurrent_database, competitor, monkeypatch, capsys, caplog
):
    engine = concurrent_database
    factory = sessionmaker(bind=engine)
    attempts = Mock(wraps=factory)
    monkeypatch.setattr(admin, "SessionLocal", attempts)
    monkeypatch.setattr(admin.getpass, "getpass", lambda prompt: NEW)
    monkeypatch.setattr("builtins.input", lambda prompt: "BOOTSTRAP")
    original_hash = admin.hash_password
    locked = False
    before = None

    def observe(conn, cursor, statement, parameters, context, executemany):
        nonlocal locked
        if statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE")):
            locked = True
        if statement.startswith(("SELECT", "INSERT")):
            assert locked, "Authoritative checks must follow the serialization lock"

    def competing_commit(password):
        nonlocal before
        attempts.assert_not_called()
        hashed = original_hash(password)
        with factory.begin() as db:
            db.add(
                User(
                    email=(
                        "  FIRST-OWNER@EXAMPLE.COM  "
                        if competitor == "email"
                        else "competing-owner@example.com"
                    ),
                    name="Competing account",
                    hashed_password=hashed,
                    is_admin=competitor != "email",
                    is_active=competitor != "inactive-admin",
                )
            )
        before = snapshot(engine)
        event.listen(engine, "before_cursor_execute", observe)
        return hashed

    monkeypatch.setattr(admin, "hash_password", competing_commit)
    try:
        assert run() != 0
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert locked
    attempts.assert_called_once_with()
    assert snapshot(engine) == before
    output = capsys.readouterr()
    expected = (
        "Requested email already exists"
        if competitor == "email"
        else "A global administrator already exists"
    )
    assert expected in output.err
    assert NEW not in output.out + output.err + caplog.text


@pytest.mark.parametrize("same_email", [False, True])
def test_concurrent_bootstraps_have_exactly_one_winner(
    concurrent_database, same_email, monkeypatch, capsys, caplog
):
    engine = concurrent_database
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(admin, "SessionLocal", factory)
    first_has_lock = threading.Event()
    second_attempted_lock = threading.Event()
    release_first = threading.Event()
    prompts = []

    def password_prompt(prompt):
        prompts.append(threading.current_thread().name)
        return NEW

    def observe_lock(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE"))
            and first_has_lock.is_set()
        ):
            second_attempted_lock.set()

    def hold_first_lock(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE"))
            and not first_has_lock.is_set()
        ):
            first_has_lock.set()
            assert release_first.wait(10)

    monkeypatch.setattr(admin.getpass, "getpass", password_prompt)
    monkeypatch.setattr("builtins.input", lambda prompt: "BOOTSTRAP")
    event.listen(engine, "before_cursor_execute", observe_lock)
    event.listen(engine, "after_cursor_execute", hold_first_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run)
            try:
                assert first_has_lock.wait(10)
                second = pool.submit(run, EMAIL if same_email else "second@example.com")
                assert second_attempted_lock.wait(10)
                assert not second.done()
            finally:
                release_first.set()
            assert first.result(timeout=10) == 0
            assert second.result(timeout=10) != 0
    finally:
        event.remove(engine, "before_cursor_execute", observe_lock)
        event.remove(engine, "after_cursor_execute", hold_first_lock)
    assert len(prompts) == 4
    with factory() as db:
        assert db.query(User).filter_by(is_admin=True).count() == 1
        assert db.query(User).count() == 1
        assert db.query(JournalEvent).count() == 1
    output = capsys.readouterr()
    assert "global administrator already exists" in output.err
    assert NEW not in output.out + output.err + caplog.text


def test_postgresql_lock_blocks_noncooperating_user_writers(
    concurrent_database, monkeypatch
):
    engine = concurrent_database
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL table lock assertion")
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(admin, "SessionLocal", factory)
    locked = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(admin.getpass, "getpass", lambda prompt: NEW)

    def hold_lock(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("LOCK TABLE"):
            locked.set()
            assert release.wait(10)

    monkeypatch.setattr("builtins.input", lambda prompt: "BOOTSTRAP")
    event.listen(engine, "after_cursor_execute", hold_lock)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            winner = pool.submit(run)
            try:
                assert locked.wait(10)
                with engine.connect() as conn:
                    # Plain reads are allowed while all INSERT/UPDATE/DELETE writers
                    # (including other tools) are blocked by the table lock.
                    assert conn.scalar(select(User.id).limit(1)) is None
                    conn.execute(text("SET LOCAL lock_timeout = '100ms'"))
                    with pytest.raises(SQLAlchemyError):
                        conn.execute(
                            User.__table__.insert().values(
                                email="unrelated@example.com",
                                name="Unrelated writer",
                                hashed_password="synthetic-not-a-real-hash",
                            )
                        )
            finally:
                release.set()
            assert winner.result(timeout=10) == 0
    finally:
        event.remove(engine, "after_cursor_execute", hold_lock)


@pytest.mark.parametrize("stage", ["user", "journal", "commit"])
def test_database_native_rollback_releases_bootstrap_lock(
    concurrent_database, stage, monkeypatch, capsys, caplog
):
    engine = concurrent_database
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(admin, "SessionLocal", factory)
    monkeypatch.setattr(admin.getpass, "getpass", lambda prompt: NEW)
    monkeypatch.setattr("builtins.input", lambda prompt: "BOOTSTRAP")

    def fail(conn, cursor, statement, parameters, context, executemany):
        if (stage == "user" and statement.startswith("INSERT INTO users")) or (
            stage == "journal" and statement.startswith("INSERT INTO journal_events")
        ):
            # Force a real server-side error, not just a Python exception.
            conn.exec_driver_sql("SELECT missing_bootstrap_test_column")

    def fail_commit(conn):
        if stage == "commit":
            raise SQLAlchemyError(NEW)

    event.listen(engine, "before_cursor_execute", fail)
    event.listen(engine, "commit", fail_commit)
    try:
        assert run() != 0
    finally:
        event.remove(engine, "before_cursor_execute", fail)
        event.remove(engine, "commit", fail_commit)
    with factory() as db:
        assert db.query(User).count() == 0
        assert db.query(JournalEvent).count() == 0
    # A fresh connection can take the released lock and commit normally.
    assert run() == 0
    assert run("second-owner@example.com") != 0
    with factory() as db:
        assert db.query(User).filter_by(is_admin=True).count() == 1
        assert db.query(JournalEvent).count() == 1
    assert_sanitized(capsys, caplog)


def _bootstrap_process(url, first, locked, second_attempted, release):
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)

    def observe(conn, cursor, statement, parameters, context, executemany):
        if not first and statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE")):
            second_attempted.set()

    def hold_lock(conn, cursor, statement, parameters, context, executemany):
        if first and statement.startswith(("LOCK TABLE", "BEGIN IMMEDIATE")):
            locked.set()
            if not release.wait(15):
                raise OSError("Local test synchronization failed")

    event.listen(engine, "before_cursor_execute", observe)
    event.listen(engine, "after_cursor_execute", hold_lock)
    try:
        with (
            patch.object(admin, "SessionLocal", factory),
            patch.object(admin.getpass, "getpass", return_value=NEW),
            patch("builtins.input", return_value="BOOTSTRAP"),
        ):
            result = run(EMAIL if first else "second@example.com")
    finally:
        engine.dispose()
    raise SystemExit(result)


def test_independent_processes_cannot_bootstrap_two_owners(concurrent_database):
    engine = concurrent_database
    context = multiprocessing.get_context("spawn")
    locked, attempted, release = (context.Event() for _ in range(3))
    url = str(engine.url)
    first = context.Process(
        target=_bootstrap_process, args=(url, True, locked, attempted, release)
    )
    second = context.Process(
        target=_bootstrap_process, args=(url, False, locked, attempted, release)
    )
    first.start()
    try:
        assert locked.wait(15)
        second.start()
        assert attempted.wait(15)
        assert second.is_alive()
        release.set()
        first.join(15)
        second.join(15)
        assert first.exitcode == 0
        assert second.exitcode == 1
    finally:
        release.set()
        for process in (first, second):
            if process.pid is not None:
                process.join(5)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
    with sessionmaker(bind=engine)() as db:
        assert db.query(User).count() == 1
        assert db.query(JournalEvent).count() == 1


def test_postgresql_lock_timeout_fails_closed(concurrent_database, monkeypatch):
    engine = concurrent_database
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL lock timeout assertion")
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(admin, "SessionLocal", factory)
    prompts = Mock(return_value=NEW)
    monkeypatch.setattr(admin.getpass, "getpass", prompts)
    monkeypatch.setattr("builtins.input", lambda prompt: "BOOTSTRAP")
    with engine.begin() as blocker:
        blocker.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
        assert run() != 0
    assert prompts.call_count == 2
    with factory() as db:
        assert db.query(User).count() == 0
        assert db.query(JournalEvent).count() == 0
