"""Read-only scheduling for repository analysis."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import Repository


def validate_cron(expression: str) -> bool:
    parts = expression.strip().split()
    return len(parts) == 5


def parse_next_run(cron_expression: str, after: datetime | None = None) -> datetime | None:
    if not validate_cron(cron_expression):
        return None
    if after is None:
        after = datetime.now(timezone.utc)
    return after


def get_scheduled_repositories(db: Session) -> list[dict]:
    repos = db.query(Repository).filter(Repository.status == "active").all()
    return [
        {
            "repository_id": r.id,
            "name": r.name,
            "url": r.url,
            "language": r.language,
            "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
        }
        for r in repos
    ]
