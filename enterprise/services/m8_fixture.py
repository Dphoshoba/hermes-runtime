"""M8 disposable fixture service (test/dev/usability scoped).

Provides a deterministic, resettable Guided Mode fixture so a non-technical
participant can run the full M8 journey against the REAL EVOSIA backend and
REAL Guided Mode API, without engineering intervention.

The fixture contains:
  * one disposable Repository (backed by validation/m8-disposable-repo on disk)
  * one security finding (hardcoded credential) adjudicated ACTIONABLE
    -> appears under "Needs Your Attention"
  * several structural findings (no adjudication)
    -> clustered into 2-3 context questions under "Needs Context"
  * one DRAFT mission ("proposed work")
  * one deterministic participant User

RESET followed by SEED always yields the identical starting state because all
ids and timestamps are fixed (deterministic). Nothing here touches production
data, real secrets, or personal information.

This module is NOT imported by the production app router graph. It is invoked
only by the facilitator CLI (enterprise/cli_m8_fixture.py) or by I6 tests, and
is gated behind EVOSIA_M8_FIXTURE=enabled so it can never silently mutate a
production database.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import get_engine, SessionLocal
from ..models import (
    Finding,
    FindingAdjudication,
    Mission,
    ProjectContext,
    Repository,
    User,
)

# ---------------------------------------------------------------------------
# Deterministic identifiers (fixed so RESET -> SEED is reproducible)
# ---------------------------------------------------------------------------

FIXTURE_MARKER = "m8_fixture"  # set in metadata_json / flags

REPO_ID = "m8-repo-00000000-0000-0000-0000-000000000001"
USER_ID = "m8-user-00000000-0000-0000-0000-000000000002"
FIND_SEC_ID = "m8-find-sec-00000000-0000-0000-0000-000000000003"
FIND_LARGE_ID = "m8-find-large-00000000-0000-0000-0000-000000000004"
FIND_DEP_ID = "m8-find-dep-00000000-0000-0000-0000-000000000005"
FIND_CFG_ID = "m8-find-cfg-00000000-0000-0000-0000-000000000006"
ADJ_SEC_ID = "m8-adj-sec-00000000-0000-0000-0000-000000000007"
MISSION_ID = "m8-mission-00000000-0000-0000-0000-000000000008"

REPO_NAME = "sample_service (M8 disposable)"
DISPOSABLE_REPO_REL = os.path.join("validation", "m8-disposable-repo")


def disposable_repo_path() -> Path:
    """Absolute path to the on-disk disposable repository.

    Resolved relative to the enterprise package root so it works regardless of
    the current working directory.
    """
    here = Path(__file__).resolve()
    # enterprise/services/m8_fixture.py -> repo root is four levels up
    root = here.parents[2]
    return (root / DISPOSABLE_REPO_REL).resolve()


# ---------------------------------------------------------------------------
# Canonical fixture data
# ---------------------------------------------------------------------------

def _repo_local_path() -> str:
    return str(disposable_repo_path())


def _build_repository() -> Repository:
    return Repository(
        id=REPO_ID,
        name=REPO_NAME,
        url=_repo_local_path(),
        default_branch="main",
        language="python",
        status="active",
        provider="local",
        commit_sha="69cc47b756779c5b0ca4b65a500f56c7ab5feff0",
        visibility="private",
        metadata_json={
            FIXTURE_MARKER: True,
            "preparation_allowed": True,  # B2 guard: prep only on disposable repo
            "local_path": _repo_local_path(),
            "is_disposable": True,
        },
    )


def _build_findings() -> list[Finding]:
    return [
        Finding(
            id=FIND_SEC_ID,
            repository_id=REPO_ID,
            finding_type="security",
            severity="high",
            category="security-credential",
            title="Hardcoded API key in configuration",
            description=(
                "src/config.py assigns a hardcoded API key string to a module-level "
                "constant. EVOSIA flags this as a security-sensitive observation."
            ),
            module="src/config.py",
            priority_score=0.9,
            effort="small",
            status="open",
            gate_state="ACTIONABLE",
            risk_band="high",
            review_rank=0.95,
            legacy_decision="ACTIONABLE",
            metadata_json={FIXTURE_MARKER: True},
        ),
        Finding(
            id=FIND_LARGE_ID,
            repository_id=REPO_ID,
            finding_type="maintainability",
            severity="medium",
            category="large-module",
            title="Large utility module",
            description="src/calc.py bundles many unrelated numeric helpers in one file.",
            module="src/calc.py",
            priority_score=0.4,
            effort="medium",
            status="open",
            metadata_json={FIXTURE_MARKER: True},
        ),
        Finding(
            id=FIND_DEP_ID,
            repository_id=REPO_ID,
            finding_type="dependency",
            severity="low",
            category="dependency-choice",
            title="Unpinned dependency choices",
            description="requirements.txt intentionally declares no third-party dependencies.",
            module="requirements.txt",
            priority_score=0.2,
            effort="small",
            status="open",
            metadata_json={FIXTURE_MARKER: True},
        ),
        Finding(
            id=FIND_CFG_ID,
            repository_id=REPO_ID,
            finding_type="configuration",
            severity="low",
            category="configuration-setup",
            title="Missing configuration items",
            description="Some configuration values are left at module-level defaults.",
            module="src/config.py",
            priority_score=0.2,
            effort="small",
            status="open",
            metadata_json={FIXTURE_MARKER: True},
        ),
    ]


def _build_adjudications() -> list[FindingAdjudication]:
    # Only the security finding is adjudicated ACTIONABLE -> "Needs Your Attention"
    now = datetime.now(timezone.utc)
    return [
        FindingAdjudication(
            id=ADJ_SEC_ID,
            finding_id=FIND_SEC_ID,
            repository_id=REPO_ID,
            classification="ACTIONABLE",
            observation_status="SUPPORTED",
            concern_status="CONCERN",
            actionability_status="ACTIONABLE",
            file_context="CONTAINS_SENSITIVE",
            operator="m8-facilitator",
            operator_notes="Flagged as needing attention for M8.",
            reviewed_at=now,
            source="human_review",
            confidence=1.0,
            evidence_snapshot={"fixture": True},
        ),
    ]


def _build_mission() -> Mission:
    return Mission(
        id=MISSION_ID,
        mission_id="M8-MISSION-001",
        repository_id=REPO_ID,
        title="Replace hardcoded API key with environment configuration",
        description=(
            "Proposed change: read the API key from an environment variable instead of "
            "a hardcoded module constant, so no secret is committed to the repository."
        ),
        mission_type="remediation",
        status="DRAFT",
        priority=1,
        created_by="m8-facilitator",
        configuration={"scope": "src/config.py"},
        metadata_json={
            FIXTURE_MARKER: True,
            "originating_finding_id": FIND_SEC_ID,
            "scope": "src/config.py",
            "validation": "Run pytest in the isolated workspace.",
            "rollback": "Discard the isolated workspace; target repository is unchanged.",
        },
    )


def _build_user() -> User:
    from . import hash_password  # local import to avoid cycle at module load

    return User(
        id=USER_ID,
        email="m8-participant@example.com",
        name="M8 Participant",
        hashed_password=hash_password("m8-participant-password"),
        is_active=True,
        is_admin=False,
    )


# ---------------------------------------------------------------------------
# Seed / Reset / Verify
# ---------------------------------------------------------------------------

def _clear_fixture(db: Session) -> None:
    """Remove all M8-fixture rows so RESET yields a clean canonical state."""
    db.query(FindingAdjudication).filter(
        FindingAdjudication.finding_id.in_([FIND_SEC_ID])
    ).delete(synchronize_session=False)
    db.query(Finding).filter(Finding.id.in_([FIND_SEC_ID, FIND_LARGE_ID, FIND_DEP_ID, FIND_CFG_ID])).delete(
        synchronize_session=False
    )
    db.query(Mission).filter(Mission.id == MISSION_ID).delete(synchronize_session=False)
    db.query(ProjectContext).filter(ProjectContext.repository_id == REPO_ID).delete(
        synchronize_session=False
    )
    db.query(Repository).filter(Repository.id == REPO_ID).delete(synchronize_session=False)
    db.query(User).filter(User.id == USER_ID).delete(synchronize_session=False)
    db.commit()


def seed_m8_fixture(db: Session | None = None) -> dict:
    """Idempotently seed (or reseed) the canonical M8 fixture.

    Returns a small summary dict. Deterministic: same ids every time.
    """
    owned = db is None
    if owned:
        db = SessionLocal()
    try:
        _clear_fixture(db)
        db.add(_build_repository())
        for f in _build_findings():
            db.add(f)
        for a in _build_adjudications():
            db.add(a)
        db.add(_build_mission())
        db.add(_build_user())
        db.commit()
        return {
            "status": "seeded",
            "repository_id": REPO_ID,
            "findings": 4,
            "actionable_findings": 1,
            "missions": 1,
            "user_id": USER_ID,
        }
    finally:
        if owned:
            db.close()


def reset_m8_fixture(db: Session | None = None) -> dict:
    """Reset to the canonical starting state. Identical outcome to SEED."""
    return seed_m8_fixture(db)


def verify_m8_fixture(db: Session | None = None) -> dict:
    """Verify the fixture contains the required Guided Mode evidence.

    Raises AssertionError if any required piece is missing (so the facilitator
    CLI and I6 tests fail loudly rather than proceed with a broken fixture).
    """
    owned = db is None
    if owned:
        db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == REPO_ID).first()
        assert repo is not None, "fixture repository missing"
        assert repo.metadata_json.get(FIXTURE_MARKER) is True, "repository not marked fixture"

        findings = db.query(Finding).filter(Finding.repository_id == REPO_ID).all()
        assert len(findings) >= 4, f"expected >=4 findings, got {len(findings)}"

        adj = (
            db.query(FindingAdjudication)
            .filter(FindingAdjudication.finding_id == FIND_SEC_ID)
            .first()
        )
        assert adj is not None and adj.classification == "ACTIONABLE", "security finding not ACTIONABLE"

        mission = db.query(Mission).filter(Mission.id == MISSION_ID).first()
        assert mission is not None, "DRAFT mission missing"
        assert mission.status == "DRAFT", f"mission status {mission.status} != DRAFT"

        user = db.query(User).filter(User.id == USER_ID).first()
        assert user is not None, "participant user missing"

        # On-disk disposable repo must exist and be a git repo
        repo_path = disposable_repo_path()
        assert repo_path.exists(), f"disposable repo missing at {repo_path}"
        assert (repo_path / ".git").exists(), "disposable repo not a git repository"

        return {
            "status": "verified",
            "repository_id": REPO_ID,
            "findings": len(findings),
            "actionable_findings": 1,
            "missions": 1,
            "disposable_repo": str(repo_path),
            "git_initialized": (repo_path / ".git").exists(),
        }
    finally:
        if owned:
            db.close()


def require_fixture_enabled() -> None:
    """Gate: refuse to run fixture ops unless explicitly enabled.

    Prevents accidental execution against a production database.
    """
    if os.environ.get("EVOSIA_M8_FIXTURE", "").lower() != "enabled":
        raise RuntimeError(
            "M8 fixture operations are disabled. Set EVOSIA_M8_FIXTURE=enabled to proceed."
        )
