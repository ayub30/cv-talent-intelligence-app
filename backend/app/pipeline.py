import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import chromadb

from .extractor import generate_employee_id, parse_cv_fields


@dataclass
class IngestResult:
    employee_id: str
    chroma_doc_id: str
    fields: dict[str, Any]


def ingest_cv(
    cv_text: str,
    filename: str,
    db: sqlite3.Connection,
    collection: chromadb.Collection,
) -> IngestResult:
    fields = parse_cv_fields(cv_text, filename)
    now = datetime.now(timezone.utc).isoformat()

    existing = db.execute(
        "SELECT id, chroma_doc_id FROM employees WHERE LOWER(name) = LOWER(?)",
        (fields["name"],),
    ).fetchone()

    if existing:
        employee_id = existing["id"]
        chroma_doc_id = existing["chroma_doc_id"]
        db.execute(
            """UPDATE employees
               SET reply_company=?, location=?, seniority=?, availability_status=?,
                   current_project_name=?, last_updated=?
               WHERE id=?""",
            (
                fields["reply_company"],
                fields["location"],
                fields["seniority"],
                fields["availability_status"],
                fields["current_project_name"],
                now,
                employee_id,
            ),
        )
        db.execute("DELETE FROM employee_skills WHERE employee_id=?", (employee_id,))
    else:
        employee_id = generate_employee_id()
        chroma_doc_id = employee_id
        db.execute(
            """INSERT INTO employees
               (id, name, reply_company, location, seniority, availability_status,
                current_project_name, last_updated, chroma_doc_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                employee_id,
                fields["name"],
                fields["reply_company"],
                fields["location"],
                fields["seniority"],
                fields["availability_status"],
                fields["current_project_name"],
                now,
                chroma_doc_id,
            ),
        )

    db.executemany(
        "INSERT INTO employee_skills (employee_id, skill, years_experience) VALUES (?, ?, ?)",
        [(employee_id, s["skill"], s["years_experience"]) for s in fields["skills"]],
    )
    db.commit()

    collection.upsert(
        ids=[chroma_doc_id],
        documents=[cv_text or fields["name"]],
        metadatas=[{"name": fields["name"], "reply_company": fields["reply_company"]}],
    )

    return IngestResult(employee_id=employee_id, chroma_doc_id=chroma_doc_id, fields=fields)
