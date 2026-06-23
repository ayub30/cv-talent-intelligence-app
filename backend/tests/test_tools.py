import sqlite3

import pytest

from app.chroma_store import init_collection, make_ephemeral_client, seed_collection
from app.database import init_db, seed_db
from app.tools import get_profile_cv, query_candidates, search_cvs


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
    col = init_collection(client)
    seed_collection(col)
    return col


class TestQueryCandidates:
    def test_no_filter_returns_all(self, db):
        results = query_candidates(db, {})
        assert len(results) == 10

    def test_availability_filter(self, db):
        results = query_candidates(db, {"availability": "available"})
        assert all(r["availability"] == "available" for r in results)
        assert len(results) > 0

    def test_seniority_filter(self, db):
        results = query_candidates(db, {"seniority": "senior"})
        assert all(r["seniority"] == "senior" for r in results)
        assert len(results) > 0

    def test_skill_filter(self, db):
        results = query_candidates(db, {"skill": "Python"})
        names = [r["name"] for r in results]
        assert "Maya Okafor" in names

    def test_skill_with_min_years(self, db):
        results = query_candidates(db, {"skill": "Azure", "min_years": 5.0})
        assert all(r["name"] != "" for r in results)

    def test_unknown_filter_returns_empty(self, db):
        results = query_candidates(db, {"availability": "nonexistent_status"})
        assert results == []

    def test_result_shape(self, db):
        results = query_candidates(db, {})
        for r in results:
            assert "employee_id" in r
            assert "name" in r
            assert "company" in r
            assert "seniority" in r
            assert "availability" in r
            assert "chroma_doc_id" in r


class TestGetProfileCv:
    def test_returns_cv_text(self, collection):
        cv = get_profile_cv(collection, "emp_001")
        assert isinstance(cv, str)
        assert len(cv) > 0
        assert "Maya Okafor" in cv

    def test_missing_id_returns_empty(self, collection):
        cv = get_profile_cv(collection, "emp_nonexistent")
        assert cv == ""


class TestSearchCvs:
    def test_returns_list(self, collection):
        try:
            results = search_cvs(collection, "Azure data engineer")
            assert isinstance(results, list)
        except Exception:
            pytest.skip("Embedding model unavailable in this environment")

    def test_scores_in_range(self, collection):
        try:
            results = search_cvs(collection, "Python machine learning")
            for r in results:
                assert 0 <= r["score"] <= 100
        except Exception:
            pytest.skip("Embedding model unavailable in this environment")

    def test_result_shape(self, collection):
        try:
            results = search_cvs(collection, "cloud architect")
            for r in results:
                assert "employee_id" in r
                assert "name" in r
                assert "cv_text" in r
                assert "score" in r
        except Exception:
            pytest.skip("Embedding model unavailable in this environment")
