import os
import shutil
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import chromadb
import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chroma_store import init_collection, make_chroma_client, seed_collection
from .database import init_db, make_connection, seed_db
from .extractor import extract_text_from_pdf, generate_employee_id, parse_cv_fields


LLM_URL = os.getenv("LLM_URL", "")
DB_PATH = os.getenv("DB_PATH", "talent.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chromadb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = make_connection(DB_PATH)
    init_db(conn)
    seed_db(conn)
    app.state.db_conn = conn

    chroma_client = make_chroma_client(CHROMA_PATH)
    collection = init_collection(chroma_client)
    seed_collection(collection)
    app.state.chroma_collection = collection

    yield

    conn.close()


app = FastAPI(title="CV Talent Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> sqlite3.Connection:
    return app.state.db_conn


def get_collection() -> chromadb.Collection:
    return app.state.chroma_collection


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    contract: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    answer: str
    matches: list[dict[str, Any]]
    source: str


class SkillOut(BaseModel):
    skill: str
    years_experience: float


class CandidateOut(BaseModel):
    id: str
    name: str
    reply_company: str
    location: str
    seniority: str
    availability_status: str
    current_project_name: str | None
    last_updated: str
    chroma_doc_id: str
    skills: list[SkillOut]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/candidates", response_model=list[CandidateOut])
def get_candidates(
    db: sqlite3.Connection = Depends(get_db),
    skill: str | None = Query(default=None),
    min_years: float | None = Query(default=None),
    seniority: str | None = Query(default=None),
    availability: str | None = Query(default=None),
    company: str | None = Query(default=None),
    location: str | None = Query(default=None),
) -> list[CandidateOut]:
    join_clause = ""
    conditions: list[str] = []
    filter_params: list[Any] = []

    if skill:
        join_clause = " JOIN employee_skills es ON e.id = es.employee_id"
        conditions.append("LOWER(es.skill) = LOWER(?)")
        filter_params.append(skill)
        if min_years is not None:
            conditions.append("es.years_experience >= ?")
            filter_params.append(min_years)

    if seniority:
        conditions.append("e.seniority = ?")
        filter_params.append(seniority)
    if availability:
        conditions.append("e.availability_status = ?")
        filter_params.append(availability)
    if company:
        conditions.append("LOWER(e.reply_company) = LOWER(?)")
        filter_params.append(company)
    if location:
        conditions.append("LOWER(e.location) = LOWER(?)")
        filter_params.append(location)

    query_sql = (
        "SELECT DISTINCT e.id, e.name, e.reply_company, e.location, e.seniority, "
        "e.availability_status, e.current_project_name, e.last_updated, e.chroma_doc_id "
        f"FROM employees e{join_clause}"
    )
    if conditions:
        query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY e.name"

    rows = db.execute(query_sql, filter_params).fetchall()

    if not rows:
        return []

    employee_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" * len(employee_ids))
    skill_rows = db.execute(
        f"SELECT employee_id, skill, years_experience FROM employee_skills WHERE employee_id IN ({placeholders})",
        employee_ids,
    ).fetchall()

    skills_by_employee: dict[str, list[SkillOut]] = {}
    for sr in skill_rows:
        skills_by_employee.setdefault(sr["employee_id"], []).append(
            SkillOut(skill=sr["skill"], years_experience=sr["years_experience"])
        )

    return [
        CandidateOut(
            id=row["id"],
            name=row["name"],
            reply_company=row["reply_company"],
            location=row["location"],
            seniority=row["seniority"],
            availability_status=row["availability_status"],
            current_project_name=row["current_project_name"],
            last_updated=row["last_updated"],
            chroma_doc_id=row["chroma_doc_id"],
            skills=skills_by_employee.get(row["id"], []),
        )
        for row in rows
    ]


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    if not LLM_URL:
        return AskResponse(
            source="mock",
            answer=(
                "LLM_URL is not configured yet. Based on the mock CV index, Maya Okafor is the strongest "
                "technical lead, Daniel Hughes covers secure platform architecture, and Aisha Rahman should "
                "own AI governance and evaluation."
            ),
            matches=[
                {
                    "name": "Maya Okafor",
                    "role": "Principal Data Engineer",
                    "score": 94,
                    "evidence": "Azure Databricks migration across clinical datasets; RAG retrieval pipelines.",
                },
                {
                    "name": "Daniel Hughes",
                    "role": "Senior Cloud Architect",
                    "score": 89,
                    "evidence": "Secure Azure landing zones, Terraform modules, SC-cleared delivery.",
                },
                {
                    "name": "Aisha Rahman",
                    "role": "AI Product Lead",
                    "score": 86,
                    "evidence": "LLM evaluation, RAG governance, stakeholder-facing AI assistant delivery.",
                },
            ],
        )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                LLM_URL,
                json={
                    "question": payload.question,
                    "contract": payload.contract,
                    "filters": payload.filters,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    data = response.json()
    return AskResponse(
        source="llm",
        answer=data.get("answer") or data.get("response") or "The LLM returned no answer field.",
        matches=data.get("matches", []),
    )


class ProfileOut(BaseModel):
    id: str
    name: str
    reply_company: str
    location: str
    seniority: str
    availability_status: str
    current_project_name: str | None
    last_updated: str
    chroma_doc_id: str
    skills: list[SkillOut]
    cv_text: str


@app.get("/profile/{employee_id}", response_model=ProfileOut)
def get_profile(
    employee_id: str,
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
) -> ProfileOut:
    row = db.execute(
        "SELECT id, name, reply_company, location, seniority, availability_status, "
        "current_project_name, last_updated, chroma_doc_id FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id!r} not found.")

    skill_rows = db.execute(
        "SELECT skill, years_experience FROM employee_skills WHERE employee_id = ?",
        (employee_id,),
    ).fetchall()

    result = collection.get(ids=[row["chroma_doc_id"]], include=["documents"])
    cv_text = result["documents"][0] if result["documents"] else ""

    return ProfileOut(
        id=row["id"],
        name=row["name"],
        reply_company=row["reply_company"],
        location=row["location"],
        seniority=row["seniority"],
        availability_status=row["availability_status"],
        current_project_name=row["current_project_name"],
        last_updated=row["last_updated"],
        chroma_doc_id=row["chroma_doc_id"],
        skills=[SkillOut(skill=sr["skill"], years_experience=sr["years_experience"]) for sr in skill_rows],
        cv_text=cv_text or "",
    )


UPLOADS_DIR = os.getenv("UPLOADS_DIR", tempfile.gettempdir() + "/talent_uploads")


class ExtractedSkill(BaseModel):
    skill: str
    years_experience: float


class IngestResponse(BaseModel):
    success: bool
    filename: str
    extracted: dict[str, Any]


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=422, detail="No file provided.")

    is_pdf = (file.content_type == "application/pdf") or file.filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=422, detail="File must be a PDF.")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    dest_path = os.path.join(UPLOADS_DIR, file.filename)
    try:
        with open(dest_path, "wb") as dest:
            shutil.copyfileobj(file.file, dest)
    finally:
        await file.close()

    cv_text = extract_text_from_pdf(dest_path)
    fields = parse_cv_fields(cv_text, file.filename)

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

    return IngestResponse(
        success=True,
        filename=file.filename,
        extracted={
            "name": fields["name"],
            "reply_company": fields["reply_company"],
            "location": fields["location"],
            "seniority": fields["seniority"],
            "availability_status": fields["availability_status"],
            "current_project_name": fields["current_project_name"],
            "skills": fields["skills"],
        },
    )
