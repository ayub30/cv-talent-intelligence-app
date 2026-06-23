"""MLX LLM loader and inference for the /ask endpoint."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MLX_MODEL_PATH = os.getenv("MLX_MODEL_PATH", "../llama-3.2-3B-fused-800")
ADAPTER_PATH = os.getenv("ADAPTER_PATH", "../adapters_talent_search")

_model = None
_tokenizer = None
_llm_loaded = False


def init_llm() -> bool:
    """Try to load the MLX model and LoRA adapter. Returns True on success."""
    global _model, _tokenizer, _llm_loaded

    if not os.path.isdir(ADAPTER_PATH):
        logger.info("Adapter directory %r not found; LLM inference disabled", ADAPTER_PATH)
        return False

    try:
        import mlx_lm

        logger.info("Loading MLX model from %r with adapter %r", MLX_MODEL_PATH, ADAPTER_PATH)
        _model, _tokenizer = mlx_lm.load(MLX_MODEL_PATH, adapter_path=ADAPTER_PATH)
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


def _build_prompt(question: str, candidates: list[dict[str, Any]]) -> str:
    context_lines = [
        f"- {c['name']} ({c['role']}, score {c['score']}): {c['evidence']}"
        for c in candidates[:5]
    ]
    context = "\n".join(context_lines) or "No candidates found."

    return (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a talent intelligence assistant helping a programme manager find the right "
        "consultants. Respond with a concise 2-3 sentence recommendation based only on the "
        "candidate data provided.<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"Question: {question}\n\n"
        f"Top candidates:\n{context}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )


def generate_answer(question: str, candidates: list[dict[str, Any]]) -> str:
    """Synthesise a natural-language answer using the loaded MLX model."""
    import mlx_lm

    prompt = _build_prompt(question, candidates)
    response: str = mlx_lm.generate(
        _model,
        _tokenizer,
        prompt=prompt,
        max_tokens=256,
        verbose=False,
    )
    return response.strip()
