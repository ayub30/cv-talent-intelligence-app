import calendar
import os
import re
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
from .llm import generate_answer, init_llm, is_loaded
from .tools import get_profile_cv, query_candidates, search_cvs


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

    init_llm()

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


class CandidatesPageOut(BaseModel):
    total: int
    items: list[CandidateOut]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/candidates", response_model=CandidatesPageOut)
def get_candidates(
    db: sqlite3.Connection = Depends(get_db),
    skill: str | None = Query(default=None),
    min_years: float | None = Query(default=None),
    seniority: str | None = Query(default=None),
    availability: str | None = Query(default=None),
    company: str | None = Query(default=None),
    location: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    _auth: str = Depends(require_auth),
) -> CandidatesPageOut:
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

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    count_sql = f"SELECT COUNT(DISTINCT e.id) FROM employees e{join_clause}{where_clause}"
    total: int = db.execute(count_sql, filter_params).fetchone()[0]

    if total == 0:
        return CandidatesPageOut(total=0, items=[])

    query_sql = (
        "SELECT DISTINCT e.id, e.name, e.reply_company, e.location, e.seniority, "
        "e.availability_status, e.current_project_name, e.last_updated, e.chroma_doc_id "
        f"FROM employees e{join_clause}{where_clause} ORDER BY e.name LIMIT ? OFFSET ?"
    )
    offset = (page - 1) * limit
    rows = db.execute(query_sql, [*filter_params, limit, offset]).fetchall()

    if not rows:
        return CandidatesPageOut(total=total, items=[])

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

    return CandidatesPageOut(
        total=total,
        items=[
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
        ],
    )


def _mock_response() -> AskResponse:
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


def _infer_role(cv_text: str, seniority: str, company: str) -> str:
    m = re.search(r"\bis an? ([A-Z][A-Za-z &\-]+?) at\b", cv_text)
    if m:
        return m.group(1).strip()
    return f"{seniority.capitalize()} at {company}" if seniority else "Professional"


def _extract_evidence(cv_text: str, question: str, max_len: int = 160) -> str:
    if not cv_text:
        return "See CV for details."
    q_words = set(question.lower().split())
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cv_text) if s.strip()]
    best, best_score = sentences[0] if sentences else cv_text, -1
    for s in sentences:
        overlap = len(q_words & set(s.lower().split()))
        if overlap > best_score:
            best_score, best = overlap, s
    return (best[:max_len] + "...") if len(best) > max_len else best


def _keyword_score(cv_text: str, question: str) -> int:
    q_words = set(question.lower().split()) - {"the", "a", "an", "for", "who", "is", "in", "of"}
    cv_words = set(cv_text.lower().split())
    overlap = len(q_words & cv_words)
    return min(75, overlap * 8)


def _heuristic_ask(
    question: str,
    filters: dict[str, Any],
    db: sqlite3.Connection,
    collection: chromadb.Collection,
) -> AskResponse:
    # Attempt semantic search; silently skip if embedding model unavailable
    semantic: dict[str, dict[str, Any]] = {}
    try:
        for m in search_cvs(collection, question, n_results=10):
            semantic[m["employee_id"]] = m
    except Exception:
        pass

    # SQL filter: apply user-supplied filters, fall back to all employees
    sql_filters = {
        k: v
        for k, v in filters.items()
        if k in ("skill", "min_years", "seniority", "availability", "company", "location")
    }
    candidates = query_candidates(db, sql_filters)
    if not candidates:
        candidates = query_candidates(db, {})

    seen: set[str] = set()
    ranked: list[dict[str, Any]] = []

    # Semantic matches first (carry higher scores)
    for emp_id, sem in semantic.items():
        if emp_id in seen:
            continue
        seen.add(emp_id)
        row = db.execute(
            "SELECT seniority, reply_company FROM employees WHERE id = ?", (emp_id,)
        ).fetchone()
        if not row:
            continue
        ranked.append(
            {
                "name": sem["name"],
                "role": _infer_role(sem["cv_text"], row["seniority"], row["reply_company"]),
                "score": sem["score"],
                "evidence": _extract_evidence(sem["cv_text"], question),
                "employee_id": emp_id,
            }
        )

    # SQL-only candidates (keyword scored)
    for c in candidates:
        emp_id = c["employee_id"]
        if emp_id in seen:
            continue
        seen.add(emp_id)
        cv = get_profile_cv(collection, c["chroma_doc_id"])
        ranked.append(
            {
                "name": c["name"],
                "role": _infer_role(cv, c["seniority"], c["company"]),
                "score": _keyword_score(cv, question),
                "evidence": _extract_evidence(cv, question),
                "employee_id": emp_id,
            }
        )

    if not ranked:
        return _mock_response()

    ranked.sort(key=lambda x: x["score"], reverse=True)
    top = ranked[:5]
    names = ", ".join(m["name"] for m in top[:3])
    answer = f"Based on CV analysis, top candidates for your query: {names}."

    return AskResponse(source="tools", answer=answer, matches=top)


@app.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
    _auth: str = Depends(require_auth),
) -> AskResponse:
    try:
        heuristic = _heuristic_ask(payload.question, payload.filters, db, collection)
        if is_loaded():
            try:
                answer = generate_answer(payload.question, heuristic.matches)
                return AskResponse(source="llm", answer=answer, matches=heuristic.matches)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("LLM inference failed: %s", exc)
        return heuristic
    except Exception:
        return _mock_response()


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


def _compute_completeness(
    name: str,
    location: str,
    seniority: str,
    availability_status: str,
    skills: list,
    cv_text: str,
    is_stale: bool,
) -> tuple[int, list[str]]:
    gaps: list[str] = []
    score = 0

    if name and name.strip():
        score += 1
    else:
        gaps.append("No name recorded")

    if location and location.strip():
        score += 1
    else:
        gaps.append("No location recorded")

    if seniority and seniority.strip():
        score += 1
    else:
        gaps.append("No seniority recorded")

    if availability_status and availability_status.strip():
        score += 1
    else:
        gaps.append("No availability status recorded")

    if len(skills) >= 1:
        score += 1
    if len(skills) < 3:
        gaps.append("Fewer than 3 skills indexed")

    if cv_text and cv_text.strip():
        score += 1
    else:
        gaps.append("No CV text indexed")

    if is_stale:
        gaps.append("CV not updated in over 6 months")

    return round(score / 6 * 100), gaps


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
    completeness: int
    gaps: list[str]


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

    is_stale = _is_stale(row["last_updated"])
    completeness, gaps = _compute_completeness(
        name=row["name"],
        location=row["location"],
        seniority=row["seniority"],
        availability_status=row["availability_status"],
        skills=skill_rows,
        cv_text=cv_text or "",
        is_stale=is_stale,
    )

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
        is_stale=is_stale,
        completeness=completeness,
        gaps=gaps,
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


class SearchResultOut(BaseModel):
    employee_id: str
    name: str
    score: int


@app.get("/search", response_model=list[SearchResultOut])
def search(
    q: str = Query(min_length=1),
    n: int = Query(default=10, ge=1, le=50),
    collection: chromadb.Collection = Depends(get_collection),
    _auth: str = Depends(require_auth),
) -> list[SearchResultOut]:
    try:
        results = search_cvs(collection, q, n_results=n)
    except Exception:
        results = []
    return [
        SearchResultOut(employee_id=r["employee_id"], name=r["name"], score=r["score"])
        for r in results
    ]


class SkillAnalyticsOut(BaseModel):
    skill: str
    supply_pct: float
    demand_pct: float


@app.get("/analytics/skills", response_model=list[SkillAnalyticsOut])
def get_skill_analytics(
    db: sqlite3.Connection = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> list[SkillAnalyticsOut]:
    total_row = db.execute("SELECT COUNT(*) as n FROM employees").fetchone()
    total = total_row["n"] if total_row else 0
    if total == 0:
        return []

    rows = db.execute(
        """
        SELECT
            LOWER(es.skill) AS skill,
            COUNT(DISTINCT es.employee_id) AS with_skill,
            COUNT(DISTINCT CASE
                WHEN e.availability_status IN ('on_project', 'rolling_off')
                THEN es.employee_id END) AS deployed_with_skill
        FROM employee_skills es
        JOIN employees e ON e.id = es.employee_id
        GROUP BY LOWER(es.skill)
        ORDER BY with_skill DESC
        LIMIT 10
        """
    ).fetchall()

    return [
        SkillAnalyticsOut(
            skill=row["skill"],
            supply_pct=round(row["with_skill"] / total * 100, 1),
            demand_pct=round(row["deployed_with_skill"] / row["with_skill"] * 100, 1)
            if row["with_skill"] > 0
            else 0.0,
        )
        for row in rows
    ]


class CompanyOut(BaseModel):
    name: str
    employee_count: int
    indexed_cv_count: int
    completeness_score: float


@app.get("/companies", response_model=list[CompanyOut])
def get_companies(
    db: sqlite3.Connection = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> list[CompanyOut]:
    rows = db.execute(
        """
        SELECT
            e.reply_company AS name,
            COUNT(DISTINCT e.id) AS employee_count,
            COUNT(DISTINCT e.chroma_doc_id) AS indexed_cv_count,
            ROUND(
                100.0 * SUM(CASE WHEN esc.skill_count >= 3 THEN 1 ELSE 0 END) / COUNT(e.id)
            ) AS completeness_score
        FROM employees e
        LEFT JOIN (
            SELECT employee_id, COUNT(*) AS skill_count
            FROM employee_skills
            GROUP BY employee_id
        ) esc ON e.id = esc.employee_id
        GROUP BY e.reply_company
        ORDER BY e.reply_company
        """
    ).fetchall()

    return [
        CompanyOut(
            name=row["name"],
            employee_count=row["employee_count"],
            indexed_cv_count=row["indexed_cv_count"],
            completeness_score=row["completeness_score"] or 0.0,
        )
        for row in rows
    ]


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


class IngestStatusRow(BaseModel):
    company: str
    total: int
    indexed: int
    failed: int
    stale: int
    status: str


def _ingest_status_label(failed: int, total: int, stale: int) -> str:
    if total == 0:
        return "Healthy"
    failed_pct = failed / total
    stale_pct = stale / total
    if failed_pct >= 0.05 or stale_pct >= 0.10:
        return "At risk"
    if failed_pct >= 0.02 or stale_pct >= 0.05:
        return "Review"
    return "Healthy"


@app.get("/ingest/status", response_model=list[IngestStatusRow])
async def ingest_status(
    db: sqlite3.Connection = Depends(get_db),
    collection: chromadb.Collection = Depends(get_collection),
    _auth: str = Depends(require_auth),
) -> list[IngestStatusRow]:
    employees = db.execute(
        "SELECT reply_company, last_updated, chroma_doc_id FROM employees ORDER BY reply_company"
    ).fetchall()

    all_chroma_ids = [e["chroma_doc_id"] for e in employees]
    if all_chroma_ids:
        chroma_result = collection.get(ids=all_chroma_ids, include=["documents"])
        indexed_ids = {
            id_
            for id_, doc in zip(chroma_result["ids"], chroma_result["documents"])
            if doc
        }
    else:
        indexed_ids: set[str] = set()

    from collections import defaultdict
    companies: dict[str, list] = defaultdict(list)
    for e in employees:
        companies[e["reply_company"]].append(e)

    result = []
    for company, members in sorted(companies.items()):
        total = len(members)
        indexed = sum(1 for e in members if e["chroma_doc_id"] in indexed_ids)
        failed = total - indexed
        stale = sum(1 for e in members if _is_stale(e["last_updated"]))
        result.append(IngestStatusRow(
            company=company,
            total=total,
            indexed=indexed,
            failed=failed,
            stale=stale,
            status=_ingest_status_label(failed, total, stale),
        ))

    return result
