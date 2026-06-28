import re
from typing import Any


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


def rank_candidates(
    question: str,
    db_candidates: list[dict[str, Any]],
    cv_lookup: dict[str, str],
) -> list[dict[str, Any]]:
    """Score and rank candidates against a question.

    db_candidates: list of dicts with keys: employee_id, name, seniority, company,
        chroma_doc_id, and optionally score (pre-computed semantic score).
    cv_lookup: maps chroma_doc_id -> cv_text.
    Returns top-5 candidates sorted by score descending.
    """
    seen: set[str] = set()
    ranked: list[dict[str, Any]] = []

    for c in db_candidates:
        emp_id = c["employee_id"]
        if emp_id in seen:
            continue
        seen.add(emp_id)
        cv = cv_lookup.get(c.get("chroma_doc_id", emp_id), "")
        score = c["score"] if "score" in c else _keyword_score(cv, question)
        ranked.append(
            {
                "name": c["name"],
                "role": _infer_role(cv, c.get("seniority", ""), c.get("company", "")),
                "score": score,
                "evidence": _extract_evidence(cv, question),
                "employee_id": emp_id,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:5]
