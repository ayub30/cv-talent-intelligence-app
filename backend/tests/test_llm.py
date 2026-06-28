from unittest.mock import MagicMock, patch

import pytest

from app.llm import LLMBackend, _build_prompt, load_llm


CANDIDATES = [
    {"name": "Maya Okafor", "role": "Data Engineer", "score": 94, "evidence": "Azure Databricks."},
    {"name": "Daniel Hughes", "role": "Cloud Architect", "score": 89, "evidence": "Terraform modules."},
]


def test_build_prompt_includes_candidates_in_system_block():
    prompt = _build_prompt("Who is best?", CANDIDATES)
    assert "Maya Okafor" in prompt
    assert "Daniel Hughes" in prompt


def test_build_prompt_includes_question_as_user_turn():
    question = "Who should I hire for Azure?"
    prompt = _build_prompt(question, CANDIDATES)
    assert question in prompt


def test_build_prompt_without_history_has_no_extra_role_headers():
    prompt = _build_prompt("Who is best?", CANDIDATES)
    # Only system + user + assistant headers — no prior turn headers
    assert prompt.count("<|start_header_id|>user<|end_header_id|>") == 1
    assert prompt.count("<|start_header_id|>assistant<|end_header_id|>") == 1


def test_build_prompt_with_history_includes_prior_turns():
    history = [
        {"role": "user", "content": "Find cloud architects"},
        {"role": "assistant", "content": "Maya Okafor is a strong fit."},
    ]
    prompt = _build_prompt("Who else?", CANDIDATES, history)
    assert "Find cloud architects" in prompt
    assert "Maya Okafor is a strong fit." in prompt


def test_build_prompt_with_history_has_correct_turn_count():
    history = [
        {"role": "user", "content": "Turn one"},
        {"role": "assistant", "content": "Response one"},
    ]
    prompt = _build_prompt("Follow-up?", CANDIDATES, history)
    # 1 history user + 1 current user = 2 user headers
    assert prompt.count("<|start_header_id|>user<|end_header_id|>") == 2
    # 1 history assistant + 1 final assistant (blank, for generation) = 2
    assert prompt.count("<|start_header_id|>assistant<|end_header_id|>") == 2


def test_build_prompt_empty_candidates_shows_no_candidates_found():
    prompt = _build_prompt("Who is best?", [])
    assert "No candidates found." in prompt


def test_load_llm_returns_none_when_model_dir_missing(tmp_path):
    import app.llm as llm_module
    original = llm_module.MLX_MODEL_PATH
    llm_module.MLX_MODEL_PATH = str(tmp_path / "nonexistent")
    try:
        result = load_llm()
        assert result is None
    finally:
        llm_module.MLX_MODEL_PATH = original


def test_load_llm_returns_none_when_mlx_not_installed(tmp_path):
    import app.llm as llm_module
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    original = llm_module.MLX_MODEL_PATH
    llm_module.MLX_MODEL_PATH = str(model_dir)
    try:
        with patch.dict("sys.modules", {"mlx_lm": None}):
            result = load_llm()
        assert result is None
    finally:
        llm_module.MLX_MODEL_PATH = original


def test_llm_backend_generate_answer_calls_mlx_generate():
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    backend = LLMBackend(model=mock_model, tokenizer=mock_tokenizer)

    mock_mlx_lm = MagicMock()
    mock_mlx_lm.generate.return_value = "  Maya Okafor is the top candidate.  "

    with patch.dict("sys.modules", {"mlx_lm": mock_mlx_lm}):
        result = backend.generate_answer("Who is best for Azure?", CANDIDATES)

    assert result == "Maya Okafor is the top candidate."
    mock_mlx_lm.generate.assert_called_once()
    call_kwargs = mock_mlx_lm.generate.call_args
    assert call_kwargs[0][0] is mock_model
    assert call_kwargs[0][1] is mock_tokenizer


def test_llm_backend_generate_answer_with_history():
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    backend = LLMBackend(model=mock_model, tokenizer=mock_tokenizer)
    history = [{"role": "user", "content": "Previous question"}]

    mock_mlx_lm = MagicMock()
    mock_mlx_lm.generate.return_value = "Response with history context."

    with patch.dict("sys.modules", {"mlx_lm": mock_mlx_lm}):
        result = backend.generate_answer("Follow-up?", CANDIDATES, history)

    assert result == "Response with history context."


def test_llm_backend_is_frozen_dataclass():
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    backend = LLMBackend(model=mock_model, tokenizer=mock_tokenizer)
    with pytest.raises((AttributeError, TypeError)):
        backend.model = MagicMock()
