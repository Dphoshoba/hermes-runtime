"""FastAPI application for the Engineering Command Center."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, sessionmaker
from .routers import auth, repositories, dashboard, journal, findings, missions, reports, scans
from .routers import trial, feedback, friction, operations, proposals, scheduling, review, guided
from .services import SECRET_KEY


def validate_security_config() -> None:
    """Fail-closed startup guard.

    Enforced at application startup (NOT at module import) so that test
    collection, TestClient, and tooling can still import the package without
    a configured secret. Real server boots refuse to start with an insecure
    default JWT secret unless explicitly running in development mode.
    """
    if not SECRET_KEY or SECRET_KEY == "hermes-enterprise-dev-secret-change-in-production":
        if os.environ.get("EVOSIA_ENV", "production").lower() != "development":
            raise RuntimeError(
                "EVOSIA_JWT_SECRET is not set to a real secret — refusing to start "
                "with an insecure default secret (set EVOSIA_ENV=development to allow "
                "the dev fallback locally)"
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — validate security config and create tables on startup."""
    validate_security_config()
    from .database import Base
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="EVOSIA Engineering Command Center",
    version="1.3.0",
    description="Observability platform for EVOSIA Enterprise",
    lifespan=lifespan,
)

# CORS — origins are server-configured. Wildcard ("*") is NEVER combined with
# credentials (invalid per Fetch spec and a CSRF/identity-leak risk). Default is
# a closed origin set; production MUST set EVOSIA_CORS_ALLOW_ORIGINS.
_cors_origins_raw = os.environ.get("EVOSIA_CORS_ALLOW_ORIGINS", "")
if _cors_origins_raw.strip() == "*":
    # Explicit operator intent: fully open, but credentials must be disabled.
    _cors_allow_origins: list[str] = ["*"]
    _cors_allow_credentials = False
elif _cors_origins_raw:
    _cors_allow_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _cors_allow_credentials = True
else:
    # Closed by default — no cross-origin access unless explicitly configured.
    _cors_allow_origins = []
    _cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(repositories.router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(journal.router, prefix="/api/journal", tags=["Journal"])
app.include_router(findings.router, prefix="/api/findings", tags=["Findings"])
app.include_router(missions.router, prefix="/api/missions", tags=["Missions"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(scans.router, prefix="/api/scans", tags=["Scans"])
app.include_router(trial.router, prefix="/api/trial", tags=["Operational Trial"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Operator Feedback"])
app.include_router(friction.router, prefix="/api/friction", tags=["Friction Journal"])
app.include_router(operations.router, prefix="/api/operations", tags=["Operations"])
app.include_router(proposals.router, prefix="/api/proposals", tags=["Feature Proposals"])
app.include_router(scheduling.router, prefix="/api/scheduling", tags=["Scheduling"])
app.include_router(review.router, prefix="/api/review", tags=["Human Review"])
app.include_router(guided.router, prefix="/api/guided", tags=["Guided Mode"])


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "1.3.0"}
