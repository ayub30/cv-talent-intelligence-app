import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


LLM_URL = os.getenv("LLM_URL", "")

app = FastAPI(title="CV Talent Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    contract: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    answer: str
    matches: list[dict[str, Any]]
    source: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
