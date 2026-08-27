"""Project authorization — short-lived tokens for project registration."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import ProjectAuthorizationToken

# Project authorization tokens are short-lived (10 minutes)
PROJECT_AUTH_TOKEN_EXPIRE_MINUTES = 10


def _hash_token(token: str) -> str:
    """Hash a token using SHA-256 for server-side storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_project_authorization_token(
    db: Session,
    device_id: str,
    user_id: str,
) -> tuple[str, datetime]:
    """Create a single-use, short-lived project authorization token.

    Returns (plaintext_token, expires_at).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PROJECT_AUTH_TOKEN_EXPIRE_MINUTES)

    # Generate a cryptographically random token
    plaintext_token = f"la_proj_{secrets.token_urlsafe(48)}"

    # Hash and store for single-use verification
    token_hash = _hash_token(plaintext_token)
    record = ProjectAuthorizationToken(
        token_hash=token_hash,
        device_id=device_id,
        user_id=user_id,
        consumed=False,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    return plaintext_token, expires_at


def verify_project_authorization_token(db: Session, token: str) -> dict:
    """Verify and consume a project authorization token.

    Enforces single-use: marks token as consumed after successful verification.
    Returns the token metadata or raises HTTPException.
    """
    token_hash = _hash_token(token)

    record = db.query(ProjectAuthorizationToken).filter(
        ProjectAuthorizationToken.token_hash == token_hash
    ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project authorization token",
        )

    if record.consumed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Project authorization token already used",
        )

    # SQLite strips timezone info — normalize both sides to naive UTC.
    expires_at = record.expires_at.replace(tzinfo=None) if record.expires_at.tzinfo else record.expires_at
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Project authorization token expired",
        )

    # Mark as consumed (single-use enforcement)
    record.consumed = True
    db.commit()

    return {
        "device_id": record.device_id,
        "user_id": record.user_id,
    }
