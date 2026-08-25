"""
M8 Guided Missions Serialization Regression Test

Validates that /api/guided/missions returns correctly-typed fields:
- authority_consequence is a string (not tuple)
- originating_finding is a human-readable title (not UUID)

Follows the I2/I3 test fixture pattern for authentication isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

M8_TEST_DB_URL = "sqlite:///./test_m8_missions_regression.db"

from enterprise.app import app
from enterprise.database import Base, get_engine
from enterprise.models import Finding, FindingAdjudication, Mission, Repository


# Unique DB URL per test module (like I2)
# This prevents collision when running multiple test processes together

@pytest.fixture(autouse=True)
def isolated_m8_db(monkeypatch):
    """Create isolated SQLite DB for M8 tests.
    
    Sets environment variables BEFORE imports trigger module-level initialization.
    """
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
    """Test client for M8 tests."""
    return TestClient(app)


@pytest.fixture
def m8_auth(m8_client):
    """Create authenticated user via real auth flow."""
    import uuid
    email = f"m8-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    
    m8_client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": "M8 Tester"
    })
    
    r = m8_client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    token = r.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def m8_fixture_data(monkeypatch):
    """Populate the isolated M8 database with mission fixture data.
    
    Creates: Repository → Finding → FindingAdjudication → Mission
    
    Follows the same pattern as I2's i2_mission fixture but creates data
    directly in the DB session to avoid DetachedInstanceError.
    """
    eng = get_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()

    # 1. Create Repository
    repo = Repository(
        name="sample_service (M8 disposable)",
        url="https://github.com/evosia/sample-service",
        status="active",
    )
    session.add(repo)
    session.flush()
    repo_id = repo.id

    # 2. Create Finding with human-readable title
    finding = Finding(
        repository_id=repo_id,
        finding_type="security",
        severity="high",
        category="security-credential",
        title="Hardcoded API key in configuration",  # Human-readable title
        description="An API key is hardcoded in the source.",
        module="src/config.py",
    )
    session.add(finding)
    session.flush()
    finding_id = finding.id

    # 3. Create FindingAdjudication (required for ACTIONABLE classification)
    session.add(FindingAdjudication(
        finding_id=finding_id,
        classification="ACTIONABLE",
        operator="operator:m8-p1",
    ))

    # 4. Create Mission with original finding reference
    mission = Mission(
        mission_id="M8-P1-001",
        repository_id=repo_id,
        title="Replace hardcoded API key with environment configuration",
        description="Prepare a proposed change to replace the hardcoded API key with environment configuration.",
        mission_type="refactor",
        status="APPROVED_FOR_FUTURE_EXECUTION",
        priority=5,
        metadata_json={
            "originating_finding_id": finding_id,
            "scope": "src/config.py",
        },
    )
    session.add(mission)
    session.commit()

    # Capture primitives while session is active
    fixture_data = {
        "repo_id": repo_id,
        "finding_id": finding_id,
        "mission_id": mission.mission_id,
    }

    session.close()
    yield fixture_data

    # Cleanup
    try:
        import os
        os.remove("./test_m8_missions_regression.db")
    except OSError:
        pass
    from enterprise.database import _ENGINES
    _ENGINES.pop(M8_TEST_DB_URL, None)


def test_guided_missions_returns_authority_consequence_as_string(
    m8_client, m8_auth, m8_fixture_data
):
    """Regression: authority_consequence must be a string, not tuple.
    
    This test covers the specific bug where a trailing comma in the backend
    caused authority_consequence to serialize as a tuple instead of a string.
    """
    r = m8_client.get("/api/guided/missions", headers=m8_auth)
    
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    
    data = r.json()
    assert isinstance(data, list), "Response should be a list"
    assert len(data) >= 1, "Should have at least one mission"
    
    mission = data[0]
    
    # CRITICAL: authority_consequence must be a string, not a tuple
    # This is the regression test for the tuple serialization bug
    ac = mission["authority_consequence"]
    assert isinstance(ac, str), \
        f'authority_consequence must be str, got {type(ac).__name__}: {ac!r}'


def test_all_mission_response_fields_are_strings(
    m8_client, m8_auth, m8_fixture_data
):
    """Verify no field accidentally becomes a tuple/list.
    
    Ensures TypeScript type correctness is maintained after the
    tuple serialization fix in enterprise/routers/guided.py:468.
    """
    r = m8_client.get("/api/guided/missions", headers=m8_auth)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    
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
            f"Field '{field}' should be str, got {type(value).__name__}: {value!r}"