"""Model-agnostic LLM backend for the /ask endpoint."""
import logging
import os
from typing import Any, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

_SYSTEM_PROMPT = (
    "You are a talent intelligence assistant helping a programme manager find the right "
    "consultants. Respond with a concise 2-3 sentence recommendation based only on the "
    "candidate data provided."
)


@runtime_checkable
class LLMBackend(Protocol):
    def generate_answer(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
    ) -> str: ...


class OllamaBackend:
    def generate_answer(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
    ) -> str:
        context_lines = [
            f"- {c['name']} ({c['role']}, score {c['score']}): {c['evidence']}"
            for c in candidates[:5]
        ]
        context = "\n".join(context_lines) or "No candidates found."
        system = f"{_SYSTEM_PROMPT}\n\nTop candidates:\n{context}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for turn in (history or []):
            messages.append({"role": turn.get("role", "user"), "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        response = httpx.post(
            f"{OLLAMA_BASE_URL}/v1/chat/completions",
            json={"model": OLLAMA_MODEL, "messages": messages, "max_tokens": 256},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


def load_llm() -> "LLMBackend | None":
    if LLM_PROVIDER != "ollama":
        logger.info("LLM_PROVIDER=%r; LLM inference disabled", LLM_PROVIDER)
        return None

    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        r.raise_for_status()
        logger.info("Ollama reachable at %s; using model %s", OLLAMA_BASE_URL, OLLAMA_MODEL)
        return OllamaBackend()
    except Exception as exc:
        logger.warning("Ollama not reachable (%s); LLM inference disabled", exc)
        return None
