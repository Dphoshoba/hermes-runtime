"""Explicit, interactive Enterprise maintenance commands (no HTTP surface)."""

from __future__ import annotations

import argparse
import getpass
import sys
import uuid
import warnings
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NoReturn

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from evosia.journal_models import _canonical_payload_sha256

from .database import SessionLocal
from .models import JournalEvent, User
from .schemas import UserCreate
from .services import hash_password


class RecoveryError(Exception):
    """A sanitized operator-facing failure."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse normally echoes rejected arguments, which may contain secrets.
        self.exit(
            2, "ERROR: Invalid arguments. Use --help; passwords are prompt-only.\n"
        )


def _reset_owner_password(db: Session, email: str) -> None:
    normalized_email = email.strip().lower()
    email_match = func.lower(func.trim(User.email)) == normalized_email
    with db.begin():
        matches = (
            db.execute(select(User).where(email_match).with_for_update())
            .scalars()
            .all()
        )
        if len(matches) != 1:
            raise RecoveryError(
                "Expected exactly one existing account; no password changed."
            )
        user = matches[0]
        if not user.is_admin or not user.is_active:
            raise RecoveryError(
                "Account must be an active global administrator; no password changed."
            )

        print(f"Account ID: {user.id}; active global administrator.")
        print("Existing user JWTs will NOT be revoked by this password change.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password: ")
            repeated = getpass.getpass("Repeat new password: ")
        if password != repeated:
            raise RecoveryError("Passwords do not match; no password changed.")
        try:
            UserCreate(email=email, name="Owner recovery", password=password)
        except ValidationError:
            raise RecoveryError(
                "Password does not meet the registration policy (8-128 characters)."
            ) from None
        # Existing bcrypt silently truncates beyond 72 UTF-8 bytes. Do not let
        # recovery appear to replace a password with an indistinguishable one.
        if len(password.encode("utf-8")) > 72:
            raise RecoveryError("Password exceeds bcrypt's 72-byte UTF-8 limit.")
        if input("Type RESET to change this account's password: ") != "RESET":
            raise RecoveryError("Confirmation declined; no password changed.")

        replacement = hash_password(password)
        count = (
            select(func.count()).select_from(User).where(email_match).scalar_subquery()
        )
        changed = (
            db.query(User)
            .filter(
                User.id == user.id,
                User.hashed_password == user.hashed_password,
                User.is_admin.is_(True),
                User.is_active.is_(True),
                email_match,
                count == 1,
            )
            # There is no password timestamp/version field. Preserve the
            # unrelated generic updated_at, including its onupdate default.
            .update(
                {User.hashed_password: replacement, User.updated_at: User.updated_at},
                synchronize_session=False,
            )
        )
        if changed != 1:
            raise RecoveryError("Account changed during recovery; no password changed.")

        payload = {"user_id": user.id, "method": "admin_cli"}
        db.add(
            JournalEvent(
                event_id=f"evt-{uuid.uuid4().hex}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="security.owner_password_reset",
                stage="security",
                actor="admin_cli",
                payload=payload,
                payload_sha256=_canonical_payload_sha256(payload),
            )
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(description="Interactive Enterprise administrator maintenance.")
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=_Parser
    )
    reset = commands.add_parser(
        "reset-owner-password", help="Reset an existing global admin password"
    )
    reset.add_argument(
        "--email", required=True, help="Existing owner/admin email (never a password)"
    )
    args = parser.parse_args(argv)

    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email.strip()))
    except ValidationError:
        print("ERROR: A valid existing account email is required.", file=sys.stderr)
        return 1

    try:
        with SessionLocal() as db:
            _reset_owner_password(db, email)
    except RecoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning, OSError):
        print(
            "ERROR: Secure interactive input unavailable or cancelled; no password changed.",
            file=sys.stderr,
        )
        return 1
    except SQLAlchemyError:
        print(
            "ERROR: Database operation failed; recovery transaction rolled back.",
            file=sys.stderr,
        )
        return 1
    except ValueError:
        print("ERROR: Password hashing failed; no password changed.", file=sys.stderr)
        return 1

    print(
        "Password reset committed with a security journal event. Existing JWTs remain valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
