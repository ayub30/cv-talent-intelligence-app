import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.auth import require_auth
from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db
from app.main import app, get_collection, get_db


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


def test_candidates_returns_all_seeded_employees(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 10


def test_candidates_response_has_total_and_items(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["items"], list)


def test_candidates_response_shape(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 200
    candidate = response.json()["items"][0]
    assert "id" in candidate
    assert "name" in candidate
    assert "reply_company" in candidate
    assert "location" in candidate
    assert "seniority" in candidate
    assert "availability_status" in candidate
    assert "last_updated" in candidate
    assert "chroma_doc_id" in candidate
    assert "skills" in candidate
    assert isinstance(candidate["skills"], list)


def test_candidates_skills_have_correct_fields(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 200
    candidates_with_skills = [c for c in response.json()["items"] if c["skills"]]
    assert len(candidates_with_skills) == 10
    skill = candidates_with_skills[0]["skills"][0]
    assert "skill" in skill
    assert "years_experience" in skill
    assert isinstance(skill["years_experience"], float)


def test_candidates_seniority_values_are_valid(test_client):
    valid_seniority = {"junior", "mid", "senior", "principal"}
    response = test_client.get("/candidates")
    for candidate in response.json()["items"]:
        assert candidate["seniority"] in valid_seniority


def test_candidates_availability_values_are_valid(test_client):
    valid_status = {"available", "on_project", "on_bench", "rolling_off"}
    response = test_client.get("/candidates")
    for candidate in response.json()["items"]:
        assert candidate["availability_status"] in valid_status


def test_filter_by_seniority(test_client):
    response = test_client.get("/candidates?seniority=junior")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Tom Bradley"
    assert all(c["seniority"] == "junior" for c in data["items"])


def test_filter_by_availability(test_client):
    response = test_client.get("/candidates?availability=available")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert all(c["availability_status"] == "available" for c in data["items"])


def test_filter_by_company(test_client):
    response = test_client.get("/candidates?company=Data Reply")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert all(c["reply_company"] == "Data Reply" for c in data["items"])


def test_filter_by_location(test_client):
    response = test_client.get("/candidates?location=London")
    assert response.status_code == 200
    data = response.json()
    assert all(c["location"] == "London" for c in data["items"])
    names = {c["name"] for c in data["items"]}
    assert "Maya Okafor" in names
    assert "Aisha Rahman" in names


def test_filter_by_skill_and_min_years(test_client):
    response = test_client.get("/candidates?skill=Python&min_years=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    names = {c["name"] for c in data["items"]}
    assert "Maya Okafor" in names
    assert "James Carter" in names
    assert "Priya Nair" in names


def test_filter_by_skill_without_min_years(test_client):
    response = test_client.get("/candidates?skill=RAG")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Aisha Rahman"


def test_filter_combination_company_and_seniority(test_client):
    response = test_client.get("/candidates?company=Data Reply&seniority=senior")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "James Carter"


def test_filter_returns_empty_when_no_match(test_client):
    response = test_client.get("/candidates?seniority=junior&company=Data Reply")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_no_filters_returns_all(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 10


def test_pagination_limit(test_client):
    response = test_client.get("/candidates?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 5


def test_pagination_page_2(test_client):
    response = test_client.get("/candidates?page=2&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 5


def test_pagination_no_overlap(test_client):
    page1 = test_client.get("/candidates?page=1&limit=5").json()["items"]
    page2 = test_client.get("/candidates?page=2&limit=5").json()["items"]
    ids1 = {c["id"] for c in page1}
    ids2 = {c["id"] for c in page2}
    assert ids1.isdisjoint(ids2)


def test_pagination_page_beyond_total(test_client):
    response = test_client.get("/candidates?page=100&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert data["items"] == []


def test_filter_combination_skill_and_location(test_client):
    response = test_client.get("/candidates?skill=Python&location=London")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert all(c["location"] == "London" for c in data["items"])
