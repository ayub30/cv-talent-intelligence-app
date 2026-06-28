import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from scripts.teacher_model import TeacherModel


def _fake_response(body: dict) -> MagicMock:
    cm = MagicMock()
    cm.__enter__ = lambda s: s
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = json.dumps(body).encode()
    return cm


def test_complete_returns_content_string():
    teacher = TeacherModel("key", "model", "https://example.com/v1/chat/completions")
    body = {"choices": [{"message": {"content": "Hello, world!"}}]}
    with patch("urllib.request.urlopen", return_value=_fake_response(body)):
        result = teacher.complete([{"role": "user", "content": "Hi"}])
    assert result == "Hello, world!"


def test_complete_returns_empty_string_when_content_is_none():
    teacher = TeacherModel("key", "model", "https://example.com/v1")
    body = {"choices": [{"message": {"content": None, "tool_calls": []}}]}
    with patch("urllib.request.urlopen", return_value=_fake_response(body)):
        result = teacher.complete([{"role": "user", "content": "Hi"}])
    assert result == ""


def test_call_includes_auth_header():
    teacher = TeacherModel("test-api-key", "model", "https://example.com/v1")
    body = {"choices": [{"message": {"content": "ok"}}]}
    captured: list = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return _fake_response(body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        teacher.complete([{"role": "user", "content": "test"}])

    assert captured[0].get_header("Authorization") == "Bearer test-api-key"


def test_call_includes_model_in_payload():
    teacher = TeacherModel("key", "my-model", "https://example.com/v1")
    body = {"choices": [{"message": {"content": "ok"}}]}
    captured: list = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return _fake_response(body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        teacher.complete([{"role": "user", "content": "test"}])

    payload = json.loads(captured[0].data)
    assert payload["model"] == "my-model"


def test_call_sends_tools_when_provided():
    teacher = TeacherModel("key", "model", "https://example.com/v1")
    tools = [{"type": "function", "function": {"name": "search_cvs"}}]
    body = {"choices": [{"message": {"content": None, "tool_calls": []}}]}
    captured: list = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return _fake_response(body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        teacher.call([{"role": "user", "content": "test"}], tools=tools)

    payload = json.loads(captured[0].data)
    assert "tools" in payload
    assert payload["tool_choice"] == "auto"


def test_call_retries_on_rate_limit_and_succeeds():
    teacher = TeacherModel("key", "model", "https://example.com/v1")
    body = {"choices": [{"message": {"content": "ok"}}]}
    attempts = [0]

    def fake_urlopen(req, timeout=None):
        attempts[0] += 1
        if attempts[0] == 1:
            raise urllib.error.HTTPError(
                url="", code=429, msg="Too Many Requests", hdrs={}, fp=BytesIO(b"")
            )
        return _fake_response(body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("time.sleep"):
            result = teacher.complete([{"role": "user", "content": "Hi"}])

    assert result == "ok"
    assert attempts[0] == 2


def test_call_raises_on_non_rate_limit_http_error():
    teacher = TeacherModel("key", "model", "https://example.com/v1")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized", hdrs={}, fp=BytesIO(b"Not authorized")
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            teacher.complete([{"role": "user", "content": "Hi"}])
            assert False, "Expected RuntimeError"
        except RuntimeError as exc:
            assert "401" in str(exc)


def test_call_raises_after_max_retries_exhausted():
    teacher = TeacherModel("key", "model", "https://example.com/v1")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs={}, fp=BytesIO(b"")
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("time.sleep"):
            try:
                teacher.complete([{"role": "user", "content": "Hi"}])
                assert False, "Expected RuntimeError"
            except RuntimeError as exc:
                assert "Max retries exceeded" in str(exc)
