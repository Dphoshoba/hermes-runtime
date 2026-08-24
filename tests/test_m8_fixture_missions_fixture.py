"""Regression test: M8 Guided Mode missions endpoint returns correct types.

Validates: authority_consequence is a string (not tuple),
originating_finding is human-readable title, response structure is correct.
"""
import pytest
from fastapi.testclient import TestClient
from enterprise.app import app
from enterprise.services.m8_fixture import seed_m8_fixture
from enterprise.database import SessionLocal, Base, engine
from unittest.mock import patch


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed M8 fixture in-memory DB."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_m8_fixture(db)
    db.close()
    yield


def test_guided_missions_returns_authority_consequence_as_string():
    """Regression test for tuple serialization bug in authority_consequence."""
    client = TestClient(app)

    # Mock authentication
    with patch("enterprise.routers.guided.get_current_user") as mock_user:
        mock_user.return_value = type("User", (), {"id": "test", "name": "Test", "email": "test@example.com"})()

        response = client.get("/api/guided/missions")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert isinstance(data, list), "Response should be a list"
    assert len(data) >= 1, "Should have at least one mission"

    mission = data[0]
    # The critical bug: authority_consequence must be a string, not a tuple
    assert isinstance(
        mission["authority_consequence"], str
    ), f'authority_consequence must be str, got {type(mission["authority_consequence"]).__name__}: {mission["authority_consequence"]!r}'

    # originating_finding should be human-readable, not a UUID
    assert isinstance(mission["originating_finding"], str)
    # Should NOT start with "m8-find-" (internal ID format)
    assert not mission["originating_finding"].startswith(
        "m8-find-"
    ), f'originating_finding should be human title, not UUID: {mission["originating_finding"]}'

    # finding_location should be a module path string
    assert isinstance(mission["finding_location"], str)


def test_guided_missions_response_types_are_correct():
    """Verify all response fields have expected types."""
    client = TestClient(app)

    with patch("enterprise.routers.guided.get_current_user") as mock_user:
        mock_user.return_value = type("User", (), {"id": "test"})()

        response = client.get("/api/guided/missions")

    assert response.status_code == 200
    data = response.json()
    mission = data[0]

    # All critical string fields
    assert isinstance(mission["mission_id"], str)
    assert isinstance(mission["title"], str)
    assert isinstance(mission["plain_title"], str)
    assert isinstance(mission["what"], str)
    assert isinstance(mission["why"], str)
    assert isinstance(mission["benefit"], str)
    assert isinstance(mission["risk"], str)
    assert isinstance(mission["scope"], str)
    assert isinstance(mission["validation"], str)
    assert isinstance(mission["rollback"], str)
    assert isinstance(mission["authority_consequence"], str)

    # Status fields
    assert isinstance(mission["status"], str)
    assert isinstance(mission["status_label"], str)
    assert mission["status"] in ["DRAFT", "APPROVED_FOR_FUTURE_EXECUTION", "PREPARED", "BLOCKED", "DEFERRED", "NEEDS_REFINEMENT"]


def test_guided_missions_never_returns_nested_structure():
    """Ensure fields are never accidentally returned as nested tuples/lists."""
    client = TestClient(app)

    with patch("enterprise.routers.guided.get_current_user") as mock_user:
        mock_user.return_value = type("User", (), {"id": "test"})()

        response = client.get("/api/guided/missions")

    assert response.status_code == 200
    data = response.json()

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
    ]

    for field in string_fields:
        value = data[0].get(field)
        assert not isinstance(
            value, (list, tuple)
        ), f"Field '{field}' should not be a list/tuple, got: {value!r}"
        assert isinstance(value, str), f"Field '{field}' should be str, got {type(value).__name__}"