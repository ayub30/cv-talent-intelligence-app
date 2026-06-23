import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.auth import require_auth
from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db, seed_users
from app.main import app, get_collection, get_db


@pytest.fixture()
def test_client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_db(conn)
    seed_users(conn)

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


def test_ask_returns_200(test_client):
    response = test_client.post("/ask", json={"question": "Who is best for Azure data migration?"})
    assert response.status_code == 200


def test_ask_response_has_correct_shape(test_client):
    response = test_client.post("/ask", json={"question": "Who is best for Azure data migration?"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert isinstance(data["matches"], list)
    assert isinstance(data["source"], str)


def test_ask_mock_source(test_client):
    response = test_client.post("/ask", json={"question": "Find the best team for this contract"})
    assert response.status_code == 200
    assert response.json()["source"] == "mock"


def test_ask_matches_have_required_fields(test_client):
    response = test_client.post("/ask", json={"question": "Find cloud architects"})
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) > 0
    for match in matches:
        assert "name" in match
        assert "role" in match
        assert "score" in match
        assert "evidence" in match


def test_ask_requires_non_empty_question(test_client):
    response = test_client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_without_auth_returns_401():
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.post("/ask", json={"question": "Who should I hire?"})
    assert response.status_code == 401
