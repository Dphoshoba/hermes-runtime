"""
M8 Guided Missions Response Serialization Regression Test

Validates that /api/guided/missions returns correctly-typed fields:
- authority_consequence is a string (not tuple)
- originating_finding is a human-readable title (not UUID)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

M8_TEST_DB_URL = "sqlite:///./test_m8_missions_regression.db"

from enterprise.app import app
from enterprise.database import Base, get_engine
from enterprise.models import Finding, FindingAdjudication, Mission, Repository, User


@pytest.fixture(autouse=True)
def isolated_m8_db(monkeypatch):
    """Create isolated in-memory DB for M8 fixture test."""
    monkeypatch.setenv("HERMES_DATABASE_URL", M8_TEST_DB_URL)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", M8_TEST_DB_URL)
    monkeypatch.setenv("EVOSIA_JWT_SECRET", "m8-test-secret")
    import enterprise.services as _svc

    monkeypatch.setattr(_svc, "SECRET_KEY", "m8-test-secret")
    import enterprise.app as _app_mod

    monkeypatch.setattr(_app_mod, "SECRET_KEY", "m8-test-secret")
    _app_mod.engine = get_engine()
    eng = _app_mod.engine
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)
    from enterprise.database import _ENGINES

    _ENGINES.pop(M8_TEST_DB_URL, None)
    import os

    try:
        os.remove("./test_m8_missions_regression.db")
    except OSError:
        pass


@pytest.fixture
def m8_client():
    return TestClient(app)


@pytest.fixture
def m8_auth(m8_client):
    """Create auth token for test user."""
    import uuid

    email = f"m8-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    m8_client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "M8 Tester"
    })
    r = m8_client.post("/api/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def m8_repo(m8_client, m8_auth):
    """Create M8 disposable repo fixture."""
    r = m8_client.post("/api/repositories", json={
        "name": "sample_service (M8 disposable)",
        "url": "https://github.com/example/sample-service",
        "status": "active",
    }, headers=m8_auth)
    return r.json()["id"]


@pytest.fixture
def m8_mission(m8_repo, isolated_m8_db):
    """Create a DRAFT mission with an originating finding."""
    eng = get_engine(M8_TEST_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()

    # Create the finding
    f1 = Finding(
        repository_id=m8_repo,
        finding_type="security",
        severity="high",
        category="security-credential",
        title="Hardcoded API key in configuration",
        description="An API key is hardcoded in the source.",
        module="src/config.py",
    )
    session.add(f1)
    session.flush()

    # Create the adjudication
    session.add(FindingAdjudication(
        finding_id=f1.id,
        classification="ACTIONABLE",
        operator="operator:m8",
    ))

    # Create the mission
    m1 = Mission(
        mission_id="M8-MISSION-001",
        repository_id=m8_repo,
        title="Replace hardcoded API key with environment configuration",
        description="Prepare a proposed change to remove a hardcoded credential.",
        mission_type="refactor",
        status="DRAFT",
        priority=5,
        metadata_json={
            "originating_finding_id": f1.id,
        },
    )
    session.add(m1)
    session.commit()
    session.close()
    return m1.id


def test_guided_missions_returns_authority_consequence_as_string(
    m8_client, m8_auth, m8_mission
):
    """Regression: authority_consequence must be a string, not tuple."""
    r = m8_client.get("/api/guided/missions", headers=m8_auth)

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    data = r.json()
    assert isinstance(data, list), "Response should be a list"
    assert len(data) >= 1, "Should have at least one mission"

    mission = data[0]

    # CRITICAL: authority_consequence must be a string
    assert isinstance(
        mission["authority_consequence"], str
    ), f'authority_consequence must be str, got {type(mission["authority_consequence"]).__name__}: {mission["authority_consequence"]!r}'

    # originating_finding should be human-readable title
    assert isinstance(mission["originating_finding"], str)
    assert not mission["originating_finding"].startswith("m8-find-"), \
        f"Should be human title, not UUID: {mission['originating_finding']}"

    # finding_location should be module path
    assert isinstance(mission["finding_location"], str)


def test_all_mission_response_fields_are_strings(
    m8_client, m8_auth, m8_mission
):
    """Verify no field accidentally becomes a tuple/list."""
    r = m8_client.get("/api/guided/missions", headers=m8_auth)
    assert r.status_code == 200
    data = r.json()
    mission = data[0]

    string_fields = [
        "authority_consequence",
        "originating_finding",
        "finding_location",
        "title",
        "plain_title",
        "what",
        "why",
        "benefit",
        "risk",
        "scope",
        "validation",
        "rollback",
        "status",
        "status_label",
    ]

    for field in string_fields:
        value = mission.get(field)
        assert not isinstance(value, (list, tuple)), \
            f"Field '{field}' should not be list/tuple: {value!r}"
        assert isinstance(value, str), \
            f"Field '{field}' should be str, got {type(value).__name__}"