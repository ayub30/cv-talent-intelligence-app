import sqlite3

import pytest
from fastapi.testclient import TestClient

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

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()
    conn.close()


def test_login_valid_credentials_returns_200(test_client):
    response = test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "admin123"})
    assert response.status_code == 200


def test_login_sets_httponly_cookie(test_client):
    response = test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "admin123"})
    assert "access_token" in response.cookies


def test_login_invalid_password_returns_401(test_client):
    response = test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_email_returns_401(test_client):
    response = test_client.post("/auth/login", json={"email": "nobody@reply.com", "password": "admin123"})
    assert response.status_code == 401


def test_protected_endpoint_without_token_returns_401(test_client):
    response = test_client.get("/candidates")
    assert response.status_code == 401


def test_protected_endpoint_with_valid_token_returns_200(test_client):
    test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "admin123"})
    response = test_client.get("/candidates")
    assert response.status_code == 200


def test_logout_clears_cookie(test_client):
    test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "admin123"})
    logout = test_client.post("/auth/logout")
    assert logout.status_code == 200


def test_after_logout_protected_endpoint_returns_401(test_client):
    test_client.post("/auth/login", json={"email": "admin@reply.com", "password": "admin123"})
    test_client.post("/auth/logout")
    response = test_client.get("/candidates")
    assert response.status_code == 401


def test_invalid_token_returns_401(test_client):
    test_client.cookies.set("access_token", "not.a.valid.jwt")
    response = test_client.get("/candidates")
    assert response.status_code == 401
