"""Database configuration — SQLAlchemy + SQLite (dev) / PostgreSQL (prod)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./hermes_enterprise.db"


def _current_url() -> str:
    """The database URL to use right now.

    Read live from the environment so that whichever test suite (or runtime)
    configured HERMES_DATABASE_URL last is authoritative, even when this module
    was first imported under a different URL.
    """
    return os.environ.get("HERMES_DATABASE_URL", DEFAULT_DATABASE_URL)


def _make_engine(url: str):
    """Build an engine for a given URL.

    In-memory SQLite databases use StaticPool so the schema/rows persist across
    connections within a process (otherwise each connection gets a fresh empty
    DB and teardown sees a "closed database").
    """
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    kwargs = dict(connect_args=connect_args, future=True)
    if url.startswith("sqlite") and url.endswith(":memory:"):
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


# URL-keyed engine cache. Different test suites set HERMES_DATABASE_URL to
# different targets (e.g. `:memory:` vs `./test_enterprise.db`); keying by URL
# gives each suite its own engine instead of reusing a stale/closed one.
_ENGINES: dict[str, object] = {}


def get_engine(url: str | None = None):
    key = url or _current_url()
    eng = _ENGINES.get(key)
    if eng is None:
        eng = _make_engine(key)
        _ENGINES[key] = eng
    return eng


# Module-level alias retained for callers that reference `engine` directly.
engine = get_engine()


def SessionLocal():
    """Session factory bound to the currently-configured engine.

    Returned as a callable so the bound engine always reflects the live
    HERMES_DATABASE_URL at call time (not the URL present at import).
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine(), future=True)()


def get_session_factory(url: str | None = None):
    """Return a sessionmaker bound to the engine for the given URL."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine(url), future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
