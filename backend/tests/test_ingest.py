import io
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.auth import require_auth
from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db
from app.main import app, get_collection, get_db


@pytest.fixture()
def test_client(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    # Re-import to pick up the env override
    import app.main as main_module
    main_module.UPLOADS_DIR = str(tmp_path)

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


def _pdf_file(name: str = "cv.pdf") -> tuple[str, tuple]:
    content = b"%PDF-1.4 fake pdf content"
    return ("file", (name, io.BytesIO(content), "application/pdf"))


def test_ingest_returns_success(test_client):
    response = test_client.post("/ingest", files=[_pdf_file()])
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_ingest_response_shape(test_client):
    response = test_client.post("/ingest", files=[_pdf_file("resume.pdf")])
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "filename" in data
    assert "extracted" in data
    extracted = data["extracted"]
    assert "name" in extracted
    assert "reply_company" in extracted
    assert "location" in extracted
    assert "seniority" in extracted
    assert "availability_status" in extracted
    assert "skills" in extracted
    assert isinstance(extracted["skills"], list)


def test_ingest_returns_filename(test_client):
    response = test_client.post("/ingest", files=[_pdf_file("my_cv.pdf")])
    assert response.status_code == 200
    assert response.json()["filename"] == "my_cv.pdf"


def test_ingest_rejects_non_pdf(test_client):
    content = b"plain text content"
    files = [("file", ("document.txt", io.BytesIO(content), "text/plain"))]
    response = test_client.post("/ingest", files=files)
    assert response.status_code == 422


def test_ingest_rejects_missing_file(test_client):
    response = test_client.post("/ingest")
    assert response.status_code == 422


def test_ingest_saves_file_to_uploads_dir(test_client, tmp_path):
    response = test_client.post("/ingest", files=[_pdf_file("saved.pdf")])
    assert response.status_code == 200
    assert (tmp_path / "saved.pdf").exists()


def test_ingest_extracted_skills_have_correct_fields(test_client):
    response = test_client.post("/ingest", files=[_pdf_file()])
    assert response.status_code == 200
    skills = response.json()["extracted"]["skills"]
    assert len(skills) > 0
    for skill in skills:
        assert "skill" in skill
        assert "years_experience" in skill
        assert isinstance(skill["years_experience"], float)


def _cv_text_for(name: str) -> str:
    return (
        f"{name}\nSenior Software Engineer in London\n"
        "Python 5 years experience. Azure 3 years. Machine Learning 2 years."
    )


def test_ingest_employee_appears_in_candidates(test_client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "extract_text_from_pdf", lambda path: _cv_text_for("Sarah Connor")
    )

    response = test_client.post("/ingest", files=[_pdf_file("sarah_connor.pdf")])
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    extracted_name = data["extracted"]["name"]

    candidates = test_client.get("/candidates").json()["items"]
    names = [c["name"] for c in candidates]
    assert extracted_name in names


def test_ingest_reupload_updates_not_duplicates(test_client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "extract_text_from_pdf", lambda path: _cv_text_for("Alice Example")
    )

    test_client.post("/ingest", files=[_pdf_file("alice.pdf")])
    test_client.post("/ingest", files=[_pdf_file("alice.pdf")])

    candidates = test_client.get("/candidates").json()["items"]
    alice_entries = [c for c in candidates if c["name"] == "Alice Example"]
    assert len(alice_entries) == 1


def test_ingest_reupload_refreshes_skills(test_client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "extract_text_from_pdf", lambda path: _cv_text_for("Bob Update")
    )
    test_client.post("/ingest", files=[_pdf_file("bob.pdf")])

    new_cv = "Bob Update\nPrincipal Engineer\nKubernetes 6 years. Docker 5 years."
    monkeypatch.setattr(main_module, "extract_text_from_pdf", lambda path: new_cv)
    test_client.post("/ingest", files=[_pdf_file("bob.pdf")])

    candidates = test_client.get("/candidates").json()["items"]
    bob = next(c for c in candidates if c["name"] == "Bob Update")
    skill_names = [s["skill"] for s in bob["skills"]]
    assert "Kubernetes" in skill_names
    assert "Docker" in skill_names
