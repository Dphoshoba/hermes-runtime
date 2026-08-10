"""FastAPI application for the Engineering Command Center."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, sessionmaker
from .routers import auth, repositories, dashboard, journal, findings, missions, reports, scans
from .routers import trial, feedback, friction, operations, proposals, scheduling, review


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — create tables on startup."""
    from .database import Base
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Hermes Engineering Command Center",
    version="1.3.0",
    description="Observability platform for Hermes Enterprise",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "1.3.0"}
