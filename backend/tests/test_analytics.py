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


def test_analytics_skills_returns_list(test_client):
    response = test_client.get("/analytics/skills")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_analytics_skills_response_shape(test_client):
    response = test_client.get("/analytics/skills")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    item = data[0]
    assert "skill" in item
    assert "supply_pct" in item
    assert "demand_pct" in item
    assert isinstance(item["supply_pct"], float)
    assert isinstance(item["demand_pct"], float)


def test_analytics_skills_supply_pct_bounds(test_client):
    response = test_client.get("/analytics/skills")
    for item in response.json():
        assert 0.0 <= item["supply_pct"] <= 100.0
        assert 0.0 <= item["demand_pct"] <= 100.0


def test_analytics_skills_python_supply(test_client):
    response = test_client.get("/analytics/skills")
    data = response.json()
    python_row = next((item for item in data if item["skill"] == "python"), None)
    assert python_row is not None
    # 6 out of 10 seeded employees have Python -> 60%
    assert python_row["supply_pct"] == 60.0


def test_analytics_skills_limited_to_top_10(test_client):
    response = test_client.get("/analytics/skills")
    assert len(response.json()) <= 10


def test_companies_returns_list(test_client):
    response = test_client.get("/companies")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_companies_response_shape(test_client):
    response = test_client.get("/companies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    company = data[0]
    assert "name" in company
    assert "employee_count" in company
    assert "indexed_cv_count" in company
    assert "completeness_score" in company


def test_companies_employee_counts_are_positive(test_client):
    response = test_client.get("/companies")
    for company in response.json():
        assert company["employee_count"] > 0
        assert company["indexed_cv_count"] >= 0
        assert 0.0 <= company["completeness_score"] <= 100.0


def test_companies_totals_match_seeded_count(test_client):
    response = test_client.get("/companies")
    data = response.json()
    total_employees = sum(c["employee_count"] for c in data)
    assert total_employees == 10


def test_companies_data_reply_has_two_employees(test_client):
    response = test_client.get("/companies")
    data = response.json()
    data_reply = next((c for c in data if c["name"] == "Data Reply"), None)
    assert data_reply is not None
    assert data_reply["employee_count"] == 2


def test_companies_indexed_cv_count_leq_employee_count(test_client):
    response = test_client.get("/companies")
    for company in response.json():
        assert company["indexed_cv_count"] <= company["employee_count"]
