"""MLX LLM loader and inference for the /ask endpoint."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MLX_MODEL_PATH = os.getenv("MLX_MODEL_PATH", "../llama-3.2-3B-fused-800")

_model = None
_tokenizer = None
_llm_loaded = False


def init_llm() -> bool:
    """Load the fused MLX model. Returns True on success."""
    global _model, _tokenizer, _llm_loaded

    if not os.path.isdir(MLX_MODEL_PATH):
        logger.info("Model directory %r not found; LLM inference disabled", MLX_MODEL_PATH)
        return False

    try:
        import mlx_lm

        logger.info("Loading fused MLX model from %r", MLX_MODEL_PATH)
        _model, _tokenizer = mlx_lm.load(MLX_MODEL_PATH)
        _llm_loaded = True
        logger.info("MLX model loaded successfully")
        return True
    except ImportError:
        logger.warning("mlx-lm is not installed; LLM inference disabled")
    except Exception as exc:
        logger.error("Failed to load MLX model: %s", exc)

    return False


def is_loaded() -> bool:
    return _llm_loaded


def _build_prompt(
    question: str,
    candidates: list[dict[str, Any]],
    history: list[dict[str, str]] | None = None,
) -> str:
    context_lines = [
        f"- {c['name']} ({c['role']}, score {c['score']}): {c['evidence']}"
        for c in candidates[:5]
    ]
    context = "\n".join(context_lines) or "No candidates found."

    turns = (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a talent intelligence assistant helping a programme manager find the right "
        "consultants. Respond with a concise 2-3 sentence recommendation based only on the "
        f"candidate data provided.\n\nTop candidates:\n{context}<|eot_id|>"
    )

    for turn in (history or []):
        role = turn.get("role", "user")
        turns += f"<|start_header_id|>{role}<|end_header_id|>\n{turn['content']}<|eot_id|>"

    turns += (
        f"<|start_header_id|>user<|end_header_id|>\n{question}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )
    return turns


def generate_answer(
    question: str,
    candidates: list[dict[str, Any]],
    history: list[dict[str, str]] | None = None,
) -> str:
    """Synthesise a natural-language answer using the loaded MLX model."""
    import mlx_lm

    prompt = _build_prompt(question, candidates, history)
    response: str = mlx_lm.generate(
        _model,
        _tokenizer,
        prompt=prompt,
        max_tokens=256,
        verbose=False,
    )
    return response.strip()
