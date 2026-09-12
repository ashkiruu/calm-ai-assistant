"""Small provider boundary for local LLM generation."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class LLMUnavailable(RuntimeError):
    """Raised when the configured model cannot produce a valid response."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    elapsed_ms: int
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    @property
    def status(self) -> dict[str, Any]: ...

    def chat(self, messages: list[dict[str, str]]) -> LLMResult: ...


class OllamaClient:
    """Synchronous Ollama client that does not contact the service on import."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("CALM_OLLAMA_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        # qwen2.5:3b was selected by scripts/benchmark_models.py: it obeyed the
        # prompt's length and single-sentence rules more closely than llama3.2
        # or phi3.5 while answering in roughly half the time.  See
        # docs/MODEL_BENCHMARK.md.
        self.model = model or os.getenv("CALM_OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("CALM_OLLAMA_TIMEOUT_SECONDS", "60")
        )

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "availability_checked_on_request": True,
        }

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": os.getenv("CALM_OLLAMA_KEEP_ALIVE", "5m"),
            "options": {
                "temperature": float(os.getenv("CALM_LLM_TEMPERATURE", "0.1")),
                "num_predict": int(os.getenv("CALM_LLM_MAX_TOKENS", "128")),
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMUnavailable(
                "The local Ollama service is unavailable. Start Ollama and try again."
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMUnavailable("Ollama returned invalid JSON.") from exc

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        text = body.get("message", {}).get("content")
        if not isinstance(text, str) or not text.strip():
            error = body.get("error")
            detail = f": {error}" if isinstance(error, str) else ""
            raise LLMUnavailable(f"Ollama returned no answer{detail}")
        return LLMResult(
            text=text.strip(),
            model=str(body.get("model") or self.model),
            elapsed_ms=elapsed_ms,
            prompt_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
        )
