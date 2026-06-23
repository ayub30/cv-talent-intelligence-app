import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

import chromadb
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chroma_store import init_collection, make_chroma_client, seed_collection
from .database import init_db, make_connection, seed_db


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
