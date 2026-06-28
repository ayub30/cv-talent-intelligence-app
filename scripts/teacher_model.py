"""Shared Groq API adapter for dataset generation scripts."""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class TeacherModel:
    """Thin HTTP adapter for a Groq-compatible chat completions endpoint."""

    def __init__(self, api_key: str, model: str, api_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._api_url = api_url

    def complete(self, messages: list[dict]) -> str:
        """Return the text content of the model's reply."""
        return self.call(messages).get("content") or ""

    def call(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_retries: int = 4,
    ) -> dict:
        """Return the assistant message dict from the API response."""
        payload: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        encoded = json.dumps(payload).encode()

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    self._api_url,
                    data=encoded,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())["choices"][0]["message"]
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"  [rate limit] waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                body = exc.read().decode(errors="replace")
                raise RuntimeError(f"Groq API {exc.code}: {body}") from exc

        raise RuntimeError("Max retries exceeded")
