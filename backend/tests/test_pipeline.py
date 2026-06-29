import sqlite3

import pytest

from app.chroma_store import init_collection, make_ephemeral_client
from app.database import init_db, seed_db
from app.pipeline import IngestResult, ingest_cv


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_db(conn)
    yield conn
    conn.close()


@pytest.fixture()
def collection():
    client = make_ephemeral_client()
    return init_collection(client)


def _cv(name: str) -> str:
    return (
        f"{name}\nSenior Software Engineer in London\n"
        "Python 5 years experience. Azure 3 years."
    )


def test_ingest_cv_returns_ingest_result(db, collection):
    result = ingest_cv(_cv("Test User"), "test.pdf", db, collection)
    assert isinstance(result, IngestResult)


def test_ingest_cv_writes_employee_to_db(db, collection):
    ingest_cv(_cv("Ada Lovelace"), "ada.pdf", db, collection)
    row = db.execute("SELECT name FROM employees WHERE LOWER(name) = 'ada lovelace'").fetchone()
    assert row is not None
    assert row["name"] == "Ada Lovelace"


def test_ingest_cv_writes_skills_to_db(db, collection):
    ingest_cv(_cv("Grace Hopper"), "grace.pdf", db, collection)
    emp = db.execute("SELECT id FROM employees WHERE LOWER(name) = 'grace hopper'").fetchone()
    skills = db.execute(
        "SELECT skill FROM employee_skills WHERE employee_id = ?", (emp["id"],)
    ).fetchall()
    skill_names = [s["skill"] for s in skills]
    assert "Python" in skill_names
    assert "Azure" in skill_names


def test_ingest_cv_upserts_to_chromadb(db, collection):
    result = ingest_cv(_cv("Alan Turing"), "alan.pdf", db, collection)
    doc = collection.get(ids=[result.chroma_doc_id], include=["documents"])
    assert doc["documents"][0] is not None
    assert "Alan Turing" in doc["documents"][0]


def test_ingest_cv_reupload_does_not_duplicate(db, collection):
    ingest_cv(_cv("Dup User"), "dup.pdf", db, collection)
    ingest_cv(_cv("Dup User"), "dup.pdf", db, collection)
    count = db.execute(
        "SELECT COUNT(*) FROM employees WHERE LOWER(name) = 'dup user'"
    ).fetchone()[0]
    assert count == 1


def test_ingest_cv_reupload_refreshes_skills(db, collection):
    ingest_cv(_cv("Refresh User"), "refresh.pdf", db, collection)

    new_cv = "Refresh User\nPrincipal Engineer\nKubernetes 6 years. Docker 5 years."
    ingest_cv(new_cv, "refresh.pdf", db, collection)

    emp = db.execute(
        "SELECT id FROM employees WHERE LOWER(name) = 'refresh user'"
    ).fetchone()
    skills = db.execute(
        "SELECT skill FROM employee_skills WHERE employee_id = ?", (emp["id"],)
    ).fetchall()
    skill_names = [s["skill"] for s in skills]
    assert "Kubernetes" in skill_names
    assert "Docker" in skill_names
    assert "Python" not in skill_names


def test_ingest_cv_fields_returned(db, collection):
    result = ingest_cv(_cv("Field Check"), "fields.pdf", db, collection)
    assert result.fields["name"] == "Field Check"
    assert result.fields["location"] == "London"
    assert result.fields["seniority"] == "senior"
    assert isinstance(result.fields["skills"], list)
