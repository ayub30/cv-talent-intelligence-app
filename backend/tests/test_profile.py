import calendar
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import require_auth
from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db
from app.main import _compute_completeness, _is_stale, app, get_collection, get_db


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
    app.dependency_overrides[require_auth] = lambda: "test@example.com"

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
    app.dependency_overrides[require_auth] = lambda: "test@example.com"

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


def test_patch_profile_single_field(test_client):
    response = test_client.patch("/profile/emp_001", json={"location": "Bristol"})
    assert response.status_code == 200
    assert response.json()["location"] == "Bristol"
    get_response = test_client.get("/profile/emp_001")
    assert get_response.json()["location"] == "Bristol"


def test_patch_profile_multiple_fields(test_client):
    response = test_client.patch(
        "/profile/emp_001",
        json={"name": "Maya O.", "seniority": "senior", "availability_status": "available"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Maya O."
    assert data["seniority"] == "senior"
    assert data["availability_status"] == "available"


def test_patch_profile_updates_last_updated(test_client):
    response = test_client.patch("/profile/emp_001", json={"location": "Edinburgh"})
    assert response.status_code == 200
    patched_ts = response.json()["last_updated"]
    assert patched_ts
    get_response = test_client.get("/profile/emp_001")
    assert get_response.json()["last_updated"] == patched_ts


def test_patch_profile_skills(test_client):
    new_skills = [{"skill": "Go", "years_experience": 2.0}, {"skill": "Rust", "years_experience": 1.0}]
    response = test_client.patch("/profile/emp_001", json={"skills": new_skills})
    assert response.status_code == 200
    returned_skills = {s["skill"] for s in response.json()["skills"]}
    assert returned_skills == {"Go", "Rust"}
    get_response = test_client.get("/profile/emp_001")
    assert {s["skill"] for s in get_response.json()["skills"]} == {"Go", "Rust"}


def test_patch_profile_clear_current_project(test_client):
    response = test_client.patch("/profile/emp_001", json={"current_project_name": None})
    assert response.status_code == 200
    assert response.json()["current_project_name"] is None


def test_patch_profile_not_found(test_client):
    response = test_client.patch("/profile/emp_999", json={"location": "London"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_profile_appears_in_candidates(test_client):
    test_client.patch("/profile/emp_001", json={"availability_status": "available"})
    candidates_response = test_client.get("/candidates")
    emp = next((c for c in candidates_response.json()["items"] if c["id"] == "emp_001"), None)
    assert emp is not None
    assert emp["availability_status"] == "available"


# --- completeness and gaps ---

@pytest.fixture()
def incomplete_client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_db(conn)
    now = datetime.now(timezone.utc).isoformat()
    # location is empty, no skills inserted — missing 3 of 6 completeness fields
    conn.execute(
        """INSERT INTO employees
           (id, name, reply_company, location, seniority, availability_status,
            current_project_name, last_updated, chroma_doc_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("emp_incomplete", "Incomplete User", "Test Co", "", "senior", "available", None, now, "emp_incomplete"),
    )
    conn.commit()

    chroma_client = make_ephemeral_client()
    collection = init_collection(chroma_client)
    seed_collection(collection)

    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_collection] = lambda: collection
    app.dependency_overrides[require_auth] = lambda: "test@example.com"

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()
    conn.close()


def test_profile_includes_completeness_and_gaps_fields(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    data = response.json()
    assert "completeness" in data
    assert "gaps" in data
    assert isinstance(data["completeness"], int)
    assert isinstance(data["gaps"], list)


def test_profile_full_profile_has_100_completeness(test_client):
    response = test_client.get("/profile/emp_001")
    assert response.status_code == 200
    data = response.json()
    assert data["completeness"] == 100
    assert data["gaps"] == []


def test_profile_missing_location_reduces_completeness(incomplete_client):
    response = incomplete_client.get("/profile/emp_incomplete")
    assert response.status_code == 200
    data = response.json()
    # name, seniority, availability_status present (3/6); location, skills, cv_text missing
    assert data["completeness"] == 50
    assert "No location recorded" in data["gaps"]


def test_profile_gaps_fewer_than_3_skills(incomplete_client):
    response = incomplete_client.get("/profile/emp_incomplete")
    data = response.json()
    assert "Fewer than 3 skills indexed" in data["gaps"]


def test_profile_gaps_no_cv_text(incomplete_client):
    response = incomplete_client.get("/profile/emp_incomplete")
    data = response.json()
    assert "No CV text indexed" in data["gaps"]


def test_profile_stale_adds_gap(stale_client):
    response = stale_client.get("/profile/emp_001")
    assert response.status_code == 200
    data = response.json()
    assert "CV not updated in over 6 months" in data["gaps"]


def test_compute_completeness_all_present():
    score, gaps = _compute_completeness("Alice", "London", "senior", "available", [1, 2, 3], "some cv", False)
    assert score == 100
    assert gaps == []


def test_compute_completeness_missing_location():
    score, gaps = _compute_completeness("Alice", "", "senior", "available", [1, 2, 3], "some cv", False)
    assert score == round(5 / 6 * 100)
    assert "No location recorded" in gaps


def test_compute_completeness_fewer_than_3_skills():
    score, gaps = _compute_completeness("Alice", "London", "senior", "available", [1], "some cv", False)
    assert "Fewer than 3 skills indexed" in gaps


def test_compute_completeness_stale_adds_gap():
    score, gaps = _compute_completeness("Alice", "London", "senior", "available", [1, 2, 3], "some cv", True)
    assert score == 100
    assert "CV not updated in over 6 months" in gaps


def test_compute_completeness_no_cv_text():
    score, gaps = _compute_completeness("Alice", "London", "senior", "available", [1, 2, 3], "", False)
    assert "No CV text indexed" in gaps
    assert score == round(5 / 6 * 100)
