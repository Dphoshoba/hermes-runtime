"""Device authentication — bootstrap tokens and device credentials."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import BootstrapToken

SECRET_KEY = os.environ.get("EVOSIA_JWT_SECRET", "hermes-enterprise-dev-secret-change-in-production")
ALGORITHM = "HS256"

# Bootstrap tokens are short-lived (5 minutes)
BOOTSTRAP_TOKEN_EXPIRE_MINUTES = 5

# Device credentials last 30 days
DEVICE_TOKEN_EXPIRE_DAYS = 30


def _hash_token(token: str) -> str:
    """Hash a token using SHA-256 for server-side storage.

    We use SHA-256 rather than bcrypt because:
    1. Bootstrap tokens are high-entropy random strings, not passwords
    2. We need exact matching, not fuzzy comparison
    3. SHA-256 is sufficient for tokens with 128+ bits of entropy
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_bootstrap_token(db: Session, device_id: str, user_id: str) -> tuple[str, datetime]:
    """Create a single-use, short-lived bootstrap token for device registration.

    Stores the hashed token in the database for single-use enforcement.
    Returns (plaintext_token, expires_at). The plaintext is returned once and never persisted.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=BOOTSTRAP_TOKEN_EXPIRE_MINUTES)

    # Generate a cryptographically random bootstrap token
    plaintext_token = f"la_boot_{secrets.token_urlsafe(48)}"

    # Hash and store for single-use verification
    token_hash = _hash_token(plaintext_token)
    record = BootstrapToken(
        token_hash=token_hash,
        device_id=device_id,
        user_id=user_id,
        consumed=False,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    return plaintext_token, expires_at


def verify_bootstrap_token(db: Session, token: str) -> dict:
    """Verify and consume a bootstrap token.

    Enforces single-use: marks token as consumed after successful verification.
    Returns the token metadata or raises HTTPException.
    """
    token_hash = _hash_token(token)

    record = db.query(BootstrapToken).filter(BootstrapToken.token_hash == token_hash).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bootstrap token",
        )

    if record.consumed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bootstrap token already used",
        )

    # SQLite strips timezone info, so record.expires_at may be naive even though
    # it was stored as aware.  Normalize both sides to naive UTC for safe comparison.
    expires_at = record.expires_at.replace(tzinfo=None) if record.expires_at.tzinfo else record.expires_at
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bootstrap token expired",
        )

    # Mark as consumed (single-use enforcement)
    record.consumed = True
    db.commit()

    return {
        "sub": record.device_id,
        "user_id": record.user_id,
        "token_type": "bootstrap",
    }


def create_device_token(device_id: str, user_id: str) -> tuple[str, datetime]:
    """Issue a device credential (JWT) after successful bootstrap exchange.

    Returns (token, expires_at).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=DEVICE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": device_id,
        "user_id": user_id,
        "token_type": "device",
        "exp": expires_at,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_at


def verify_device_token(token: str) -> dict:
    """Verify and decode a device credential.

    Returns the decoded payload or raises HTTPException.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device token",
        )

    if payload.get("token_type") != "device":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return payload
