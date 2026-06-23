"""Tool functions for the /ask agentic loop."""
import sqlite3
from typing import Any

import chromadb


def search_cvs(
    collection: chromadb.Collection,
    query: str,
    filters: dict[str, Any] | None = None,
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Semantic search against ChromaDB employee CV collection.

    Returns a list of dicts with keys: employee_id, name, cv_text, score (0-100).
    """
    where: dict | None = None
    if filters and "company" in filters:
        where = {"reply_company": {"$eq": filters["company"]}}

    kwargs: dict[str, Any] = {
        "query_texts": [query],
        "n_results": n_results,
        "include": ["documents", "distances", "metadatas"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    if not results["ids"] or not results["ids"][0]:
        return []

    matches = []
    for doc_id, doc, dist, meta in zip(
        results["ids"][0],
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0],
    ):
        # Cosine distance: 0 = identical, 2 = opposite → convert to 0-100 score
        score = max(0, min(100, round((1.0 - dist / 2.0) * 100)))
        matches.append(
            {
                "employee_id": doc_id,
                "name": meta.get("name", ""),
                "cv_text": doc or "",
                "score": score,
            }
        )
    return sorted(matches, key=lambda m: m["score"], reverse=True)


def query_candidates(
    db: sqlite3.Connection,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Structured filter query against SQLite employees + employee_skills tables.

    Supported filter keys: skill, min_years, seniority, availability, company, location.
    Returns list of dicts with keys: employee_id, name, company, seniority,
    availability, chroma_doc_id.
    """
    join_clause = ""
    conditions: list[str] = []
    params: list[Any] = []

    if "skill" in filters:
        join_clause = " JOIN employee_skills es ON e.id = es.employee_id"
        conditions.append("LOWER(es.skill) = LOWER(?)")
        params.append(filters["skill"])
        if "min_years" in filters:
            conditions.append("es.years_experience >= ?")
            params.append(filters["min_years"])

    col_map = {
        "seniority": "e.seniority",
        "availability": "e.availability_status",
        "company": "e.reply_company",
        "location": "e.location",
    }
    for field, col in col_map.items():
        if field in filters:
            conditions.append(f"LOWER({col}) = LOWER(?)")
            params.append(filters[field])

    sql = (
        "SELECT DISTINCT e.id, e.name, e.reply_company, e.seniority, "
        "e.availability_status, e.chroma_doc_id "
        f"FROM employees e{join_clause}"
    )
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY e.name"

    rows = db.execute(sql, params).fetchall()
    return [
        {
            "employee_id": row["id"],
            "name": row["name"],
            "company": row["reply_company"],
            "seniority": row["seniority"],
            "availability": row["availability_status"],
            "chroma_doc_id": row["chroma_doc_id"],
        }
        for row in rows
    ]


def get_profile_cv(collection: chromadb.Collection, employee_id: str) -> str:
    """Fetch full CV text from ChromaDB for the given employee ID."""
    result = collection.get(ids=[employee_id], include=["documents"])
    docs = result.get("documents") or []
    return docs[0] if docs else ""
