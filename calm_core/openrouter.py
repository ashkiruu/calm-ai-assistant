"""Hosted-model provider boundary, for benchmarking many models at once.

The local 6 GB card caps testing near an 8B model, which is not enough to answer
"is a bigger model better at Filipino?" -- the question the corrected benchmark
actually poses. OpenRouter fronts hundreds of models behind one OpenAI-shaped
endpoint, so a sweep needs one key rather than one GPU per model.

**This provider sends the learner question to a third party.** `OllamaClient`
does not. That difference is reported as `local_only` in `status`, which
`RAGChatService.status` spreads into `/health`, so which side of the boundary a
deployment is on is a runtime fact rather than a claim in a comment. It used to
be only a claim in a comment, and the comment went out of date.

Standard library only, deliberately: `calm_core` has no third-party imports, and
that is what lets the Colab benchmark bundle run with no `pip install` at all.
Reaching for `requests` or `httpx` here would break that quietly.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .llm import LLMResult, LLMUnavailable


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3-32b"

#: Statuses worth trying again. 429 is the rate limiter; 5xx is the upstream
#: provider failing rather than the request being wrong. Everything else is a
#: fault in the request itself and a retry would just repeat it.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
#: The only status that means "your request was wrong", as opposed to "the
#: service is unavailable". It is the one case where resending a *different*
#: payload is reasonable; resending after an outage is just doubling the wait.
REJECTED_PARAMETER_STATUS = 400


def _is_rejected_parameter(failure: LLMUnavailable) -> bool:
    """True when the service rejected the request itself, not the connection."""

    return getattr(failure, "status_code", None) == REJECTED_PARAMETER_STATUS
DEFAULT_MAX_ATTEMPTS = 4

#: A bad key and a dead server are not the same problem, and telling them apart
#: is the entire reason this client does not reuse Ollama's error text. Note
#: urllib.error.HTTPError subclasses URLError, so catching URLError alone would
#: flatten all of these back into one message.
STATUS_HELP = {
    400: "OpenRouter rejected the request as malformed.",
    401: "OpenRouter rejected the API key. Check OPENROUTER_API_KEY.",
    402: "The OpenRouter account is out of credit.",
    403: "OpenRouter refused this model. It may need extra access or a data policy change.",
    404: "OpenRouter does not know that model id.",
    429: "OpenRouter rate limit reached.",
}


class OpenRouterClient:
    """OpenAI-compatible client for OpenRouter, shaped like `OllamaClient`."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        api_key: str | None = None,
        max_attempts: int | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("CALM_OPENROUTER_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self.model = model or os.getenv("CALM_OPENROUTER_MODEL", DEFAULT_MODEL)
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("CALM_OPENROUTER_TIMEOUT_SECONDS", "120")
        )
        # Read at call time, not construction time: the benchmark builds a
        # client per model and a missing key should fail once the request is
        # made, with a message naming the variable, rather than at import.
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        # Configurable because attempts x timeout is what a learner waits for.
        # A benchmark sweep wants persistence; a child in a headset wants the
        # reviewed fallback before Unity's own 40s timeout fires, otherwise the
        # request is abandoned and the failure is reported as an unreachable
        # server rather than an unreachable model.
        self.max_attempts = max(
            1,
            max_attempts
            if max_attempts is not None
            else int(os.getenv("CALM_OPENROUTER_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS))),
        )
        # Reasoning is OFF by default, which is the opposite of most defaults
        # and deliberate here.  A CALM answer is at most 45 words of reviewed
        # safety guidance; there is nothing to reason about, and reasoning
        # tokens come out of the SAME max_tokens budget as the answer.  Measured
        # consequence with it on: DeepSeek V4 Pro answered only 19 of 44
        # benchmark questions and ling-3.0-flash only 19 -- the rest spent the
        # budget thinking, returned empty content, and were scored as the
        # pipeline's deterministic fallback rather than as the model.
        #
        # "none" disables it; "exclude" would only hide the tokens while still
        # billing them and still consuming the budget, which fixes nothing.
        # Set CALM_OPENROUTER_REASONING to low/medium/high to re-enable, or to
        # "default" to send no reasoning parameter at all.
        effort = (
            reasoning_effort
            if reasoning_effort is not None
            else os.getenv("CALM_OPENROUTER_REASONING", "none")
        ).strip().lower()
        self.reasoning_effort = "" if effort in {"", "default"} else effort

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": "openrouter",
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "availability_checked_on_request": True,
            # The learner question leaves this machine. Surfaced rather than
            # documented, because documentation does not fail a test.
            "local_only": False,
            "api_key_configured": bool(self._api_key),
            "reasoning_effort": self.reasoning_effort or "default",
        }

    def _request(self, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                # Optional on OpenRouter's side; identifies the caller in their
                # dashboards, which is useful when a sweep misbehaves.
                "HTTP-Referer": "https://github.com/ashkiruu/calm-ai-assistant",
                "X-Title": "CALM AI Assistant",
            },
            method="POST",
        )

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        if not self._api_key:
            raise LLMUnavailable(
                "OPENROUTER_API_KEY is not set, so no hosted model can be reached."
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Same env vars the Ollama client reads, so a model comparison is
            # not silently also a sampling-settings comparison.
            "temperature": float(os.getenv("CALM_LLM_TEMPERATURE", "0.1")),
            "max_tokens": int(os.getenv("CALM_LLM_MAX_TOKENS", "128")),
        }
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}

        started = time.perf_counter()
        try:
            body = self._send_with_retry(self._request(payload))
        except LLMUnavailable as first_failure:
            # Some models declare reasoning mandatory and reject effort:"none"
            # with a 400.  Falling back to the model's own default is better
            # than losing the model from the comparison entirely.
            #
            # This retry MUST be limited to that one case.  The original guard
            # was `if not self.reasoning_effort: raise`, and the default effort
            # is the string "none" -- non-empty, therefore truthy -- so the
            # guard never fired and *every* failure re-ran the whole ladder,
            # including "OpenRouter is unreachable".  On a network that drops
            # packets rather than refusing them that is 4 x 120s + backoff,
            # twice: about sixteen minutes of server-side work for one child's
            # question, long after Unity gave up at 40s.  The endpoint is a sync
            # def, so each one holds an AnyIO worker thread and enough of them
            # stop /health answering at all.
            if not self.reasoning_effort or not _is_rejected_parameter(first_failure):
                raise
            payload.pop("reasoning", None)
            body = self._send_with_retry(self._request(payload))
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        choices = body.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message") or {}).get("content") or ""
        if not isinstance(text, str) or not text.strip():
            error = body.get("error")
            if isinstance(error, dict):
                error = error.get("message")
            detail = f": {error}" if isinstance(error, str) else ""
            raise LLMUnavailable(f"OpenRouter returned no answer{detail}")

        usage = body.get("usage") or {}
        return LLMResult(
            text=text.strip(),
            # OpenRouter echoes the model it actually routed to, which can
            # differ from what was asked for when a variant is aliased.
            model=str(body.get("model") or self.model),
            elapsed_ms=elapsed_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            # Same meaning as Ollama's done_reason; reasoning models hit this
            # often, because reasoning and content share the max_tokens budget.
            truncated=(choices[0].get("finish_reason") == "length"),
        )

    def _send_with_retry(self, request: urllib.request.Request) -> dict[str, Any]:
        """POST, retrying the statuses that are worth retrying.

        A 44-question sweep across a dozen models is long enough that one
        rate-limit response is likely, and the benchmark abandons a model's
        entire run on a single error. Without this, a sweep dies halfway and
        the partial result looks like a model failure.
        """

        last: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code not in RETRY_STATUSES or attempt == self.max_attempts - 1:
                    # The status travels with the exception so a caller can tell
                    # "the request was malformed" from "the service is not
                    # there". Sniffing the message text for a number would break
                    # the moment the wording changed.
                    failure = LLMUnavailable(self._describe(exc))
                    failure.status_code = exc.code
                    raise failure from exc
                time.sleep(self._backoff(exc, attempt))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt == self.max_attempts - 1:
                    raise LLMUnavailable(
                        f"OpenRouter is unreachable: {exc}"
                    ) from exc
                time.sleep(2.0 * (attempt + 1))
            except json.JSONDecodeError as exc:
                raise LLMUnavailable("OpenRouter returned invalid JSON.") from exc

        raise LLMUnavailable(f"OpenRouter request failed: {last}")

    @staticmethod
    def _backoff(exc: urllib.error.HTTPError, attempt: int) -> float:
        """Seconds to wait, preferring the server's own instruction."""

        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                # Cap it: a provider asking for several minutes should fail the
                # sweep visibly rather than make it look hung.
                return min(float(retry_after), 30.0)
            except (TypeError, ValueError):
                pass
        return min(2.0 * (2**attempt), 30.0)

    def _describe(self, exc: urllib.error.HTTPError) -> str:
        help_text = STATUS_HELP.get(exc.code, f"OpenRouter returned HTTP {exc.code}.")
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = payload.get("error")
            if isinstance(message, dict):
                message = message.get("message")
            if isinstance(message, str) and message.strip():
                detail = f" {message.strip()}"
        except Exception:  # noqa: BLE001 - a body is a bonus, never required
            pass
        return f"{help_text}{detail}"
