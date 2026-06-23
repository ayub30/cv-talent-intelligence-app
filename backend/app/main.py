import calendar
import os
import shutil
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import chromadb
from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import create_access_token, require_auth, verify_password
from .chroma_store import init_collection, make_chroma_client, seed_collection
from .database import init_db, make_connection, seed_db, seed_users
from .extractor import extract_text_from_pdf, generate_employee_id, parse_cv_fields


DB_PATH = os.getenv("DB_PATH", "talent.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chromadb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = make_connection(DB_PATH)
    init_db(conn)
    seed_db(conn)
    seed_users(conn)
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


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    row = db.execute(
        "SELECT email, password_hash FROM users WHERE email = ?", (payload.email,)
    ).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=row["email"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=86400)
    return {"message": "logged in"}


@app.post("/auth/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("access_token")
    return {"message": "logged out"}


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
    _auth: str = Depends(require_auth),
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
def ask(payload: AskRequest, _auth: str = Depends(require_auth)) -> AskResponse:
    return AskResponse(
        source="mock",
        answer=(
            "Based on the CV index, Maya Okafor is the strongest technical lead, "
            "Daniel Hughes covers secure platform architecture, and Aisha Rahman should "
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


STALE_MONTHS = 6


def _is_stale(last_updated_iso: str) -> bool:
    try:
        last_updated = datetime.fromisoformat(last_updated_iso)
    except ValueError:
        return False
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    threshold_month = now.month - STALE_MONTHS
    threshold_year = now.year
    if threshold_month <= 0:
        threshold_month += 12
        threshold_year -= 1
    max_day = calendar.monthrange(threshold_year, threshold_month)[1]
    threshold = now.replace(
        year=threshold_year,
        month=threshold_month,
        day=min(now.day, max_day),
        microsecond=0,
    )
    return last_updated <= threshold


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
    is_stale: bool


@app.get("/profile/{employee_id}", response_model=ProfileOut)
def get_profile(
    employee_id: str,
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
    _auth: str = Depends(require_auth),
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
        is_stale=_is_stale(row["last_updated"]),
    )


class ProfilePatch(BaseModel):
    name: str | None = None
    reply_company: str | None = None
    location: str | None = None
    seniority: str | None = None
    availability_status: str | None = None
    current_project_name: str | None = None
    skills: list[SkillOut] | None = None


@app.patch("/profile/{employee_id}", response_model=ProfileOut)
def patch_profile(
    employee_id: str,
    patch: ProfilePatch,
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
    _auth: str = Depends(require_auth),
) -> ProfileOut:
    row = db.execute(
        "SELECT id FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id!r} not found.")

    now = datetime.now(timezone.utc).isoformat()

    update_data = patch.model_dump(exclude_unset=True)
    skills_to_update = update_data.pop("skills", None)

    set_parts: dict[str, Any] = {"last_updated": now}
    set_parts.update(update_data)

    set_clause = ", ".join(f"{k} = ?" for k in set_parts)
    db.execute(
        f"UPDATE employees SET {set_clause} WHERE id = ?",
        [*set_parts.values(), employee_id],
    )

    if skills_to_update is not None:
        db.execute("DELETE FROM employee_skills WHERE employee_id = ?", (employee_id,))
        if skills_to_update:
            db.executemany(
                "INSERT INTO employee_skills (employee_id, skill, years_experience) VALUES (?, ?, ?)",
                [(employee_id, s["skill"], s["years_experience"]) for s in skills_to_update],
            )

    db.commit()

    return get_profile(employee_id, db, collection)


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
    _auth: str = Depends(require_auth),
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
