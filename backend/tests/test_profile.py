import calendar
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db
from app.main import _is_stale, app, get_collection, get_db


@pytest.fixture()
def test_client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_db(conn)

    chroma_client = make_ephemeral_client()
    collection = init_collection(chroma_client)
    seed_collection(collection)

    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_collection] = lambda: collection

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()
    conn.close()


def test_profile_returns_combined_response_shape(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "emp_001"
    assert data["name"] == "Maya Okafor"
    assert data["reply_company"] == "Data Reply"
    assert data["location"] == "London"
    assert data["seniority"] == "principal"
    assert "availability_status" in data
    assert "last_updated" in data
    assert "chroma_doc_id" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) > 0
    assert "cv_text" in data


def test_profile_skills_have_correct_fields(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    skill = response.json()["skills"][0]
    assert "skill" in skill
    assert "years_experience" in skill
    assert isinstance(skill["years_experience"], float)


def test_profile_cv_text_is_non_empty(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    assert response.json()["cv_text"] != ""


def test_profile_cv_text_contains_employee_name(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    assert "Maya Okafor" in response.json()["cv_text"]


def test_profile_returns_404_for_missing_employee(test_client):
    response = test_client.get("/profile/emp_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_profile_different_employee(test_client):
    response = test_client.get("/profile/emp_003")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Aisha Rahman"
    assert data["reply_company"] == "Machine Learning Reply"
    assert any(s["skill"] == "LLM Evaluation" for s in data["skills"])


def test_profile_includes_is_stale_field(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    assert "is_stale" in response.json()


def test_profile_recently_updated_is_not_stale(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    assert response.json()["is_stale"] is False


def _six_months_ago_iso(offset_days: int = 0) -> str:
    now = datetime.now(timezone.utc)
    month = now.month - 6
    year = now.year
    if month <= 0:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    threshold = now.replace(year=year, month=month, day=min(now.day, max_day), microsecond=0)
    from datetime import timedelta
    return (threshold - timedelta(days=offset_days)).isoformat()


@pytest.fixture()
def stale_client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_db(conn)
    # backdating emp_001 to exactly 6 months ago (boundary — should be stale)
    conn.execute("UPDATE employees SET last_updated = ? WHERE id = 'emp_001'", (_six_months_ago_iso(0),))
    # backdating emp_002 to 7 months ago (clearly stale)
    conn.execute("UPDATE employees SET last_updated = ? WHERE id = 'emp_002'", (_six_months_ago_iso(30),))
    conn.commit()

    chroma_client = make_ephemeral_client()
    collection = init_collection(chroma_client)
    seed_collection(collection)

    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_collection] = lambda: collection

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()
    conn.close()


def test_profile_exactly_six_months_ago_is_stale(stale_client):
    response = stale_client.get("/profile/emp_001")
    assert response.status_code == 200
    assert response.json()["is_stale"] is True


def test_profile_more_than_six_months_ago_is_stale(stale_client):
    response = stale_client.get("/profile/emp_002")
    assert response.status_code == 200
    assert response.json()["is_stale"] is True


def test_is_stale_helper_fresh():
    now_iso = datetime.now(timezone.utc).isoformat()
    assert _is_stale(now_iso) is False


def test_is_stale_helper_boundary():
    now = datetime.now(timezone.utc)
    month = now.month - 6
    year = now.year
    if month <= 0:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    boundary = now.replace(year=year, month=month, day=min(now.day, max_day), microsecond=0)
    assert _is_stale(boundary.isoformat()) is True


def test_is_stale_helper_one_day_before_boundary():
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    month = now.month - 6
    year = now.year
    if month <= 0:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    boundary = now.replace(year=year, month=month, day=min(now.day, max_day), microsecond=0)
    just_before = boundary + timedelta(days=1)
    assert _is_stale(just_before.isoformat()) is False
