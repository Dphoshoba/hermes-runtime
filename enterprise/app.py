"""FastAPI application for the Engineering Command Center."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
    """Lightweight liveness probe — always returns 200 when the process is up."""
    return {"status": "ok", "version": "1.3.0"}


@app.get("/api/ready")
def readiness_check() -> dict[str, str]:
    """Readiness probe — verifies database connectivity.

    Returns 200 when the database is reachable, 503 otherwise.
    Never exposes database URLs or credentials.
    """
    try:
        from .database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unavailable"}


@app.get("/api/version")
def version_info() -> dict[str, str]:
    """Build provenance for the running backend (diagnostic, no secrets)."""
    from .services.build_info import provenance

    return {"version": "1.3.0", **provenance()}


# ---------------------------------------------------------------------------
# Single-origin static frontend serving.
#
# When EVOSIA is deployed as a container, the built frontend (SPA) lives in
# /app/static (see Dockerfile). Serving it from the same origin as the API
# removes all cross-origin/CORS concerns for the remote M8 participant: one
# HTTPS origin, no wildcard credentials. API routes are registered above and
# take precedence; this catch-all only handles everything else.
# ---------------------------------------------------------------------------

def _static_dir() -> Path | None:
    """Locate the built frontend assets.

    Resolution order:
      1. EVOSIA_STATIC_DIR env (explicit override)
      2. /app/static                      (Docker container layout)
      3. <repo_root>/enterprise-ui/dist   (local `npm run build` layout)
    """
    for candidate in (
        os.environ.get("EVOSIA_STATIC_DIR"),
        "/app/static",
        str(Path(__file__).resolve().parents[1] / "enterprise-ui" / "dist"),
    ):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return None


_STATIC_DIR = _static_dir()
_STATIC_INDEX = (_STATIC_DIR / "index.html") if _STATIC_DIR else None


@app.api_route("/{full_path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def spa_catch_all(request: Request, full_path: str) -> FileResponse:
    """Serve the SPA.

    - Unknown API endpoints (/api/*) → 404, regardless of HTTP method. This is
      critical: the catch-all MUST NOT mask the absence of execute/merge/deploy
      endpoints. Those paths must 404 so the authority-boundary tests can prove
      they do not exist.
    - Existing static asset → return it (GET/HEAD).
    - Anything else (client-side routes) → index.html (GET/HEAD).
    - Non-GET/HEAD on non-asset paths → 405 (method not allowed).
    """
    if not _STATIC_DIR or not _STATIC_INDEX:
        raise HTTPException(status_code=404, detail="Frontend not available")

    # Unknown API endpoints must genuinely 404 — every method.
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    # Only GET/HEAD serve the SPA / static assets.
    if request.method not in ("GET", "HEAD"):
        raise HTTPException(status_code=405, detail="Method not allowed")

    # Prevent path traversal: resolve within _STATIC_DIR only.
    requested = (_STATIC_DIR / full_path).resolve()
    try:
        requested.relative_to(_STATIC_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    if requested.is_file():
        return FileResponse(str(requested))

    # SPA fallback.
    return FileResponse(str(_STATIC_INDEX))
