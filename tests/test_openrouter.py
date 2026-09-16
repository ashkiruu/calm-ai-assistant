"""OpenRouter provider contract, without touching the network.

The point of these tests is the part that differs from the Ollama client: a
hosted API fails in several distinguishable ways, and the failure text is what
somebody reads at 9pm when a sweep stops. A bad key reported as "the service is
unavailable" costs an hour.
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from calm_core.llm import LLMUnavailable
from calm_core.openrouter import OpenRouterClient


MESSAGES = [
    {"role": "system", "content": "policy"},
    {"role": "user", "content": "{}"},
]


def ok_body(text: str = "Stay under the table.") -> io.BytesIO:
    return io.BytesIO(
        json.dumps(
            {
                "model": "qwen/qwen3-32b",
                "choices": [{"message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": 1191, "completion_tokens": 21},
            }
        ).encode("utf-8")
    )


class FakeResponse:
    """Context-manager shim matching what urlopen returns."""

    def __init__(self, stream: io.BytesIO) -> None:
        self._stream = stream

    def __enter__(self):
        return self._stream

    def __exit__(self, *exc_info) -> bool:
        return False


def http_error(code: int, message: str = "nope") -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message}}).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=code,
        msg=message,
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )


class OpenRouterClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = OpenRouterClient(
            model="qwen/qwen3-32b", api_key="test-key", timeout_seconds=5
        )

    def test_status_declares_that_questions_leave_the_machine(self) -> None:
        """The whole reason this flag exists, so assert it rather than trust it."""

        status = self.client.status
        self.assertEqual(status["provider"], "openrouter")
        self.assertFalse(status["local_only"])
        self.assertTrue(status["api_key_configured"])

    def test_successful_call_maps_the_openai_shape(self) -> None:
        with patch("urllib.request.urlopen", return_value=FakeResponse(ok_body())):
            result = self.client.chat(MESSAGES)

        self.assertEqual(result.text, "Stay under the table.")
        self.assertEqual(result.model, "qwen/qwen3-32b")
        self.assertEqual(result.prompt_tokens, 1191)
        self.assertEqual(result.output_tokens, 21)

    def test_missing_key_names_the_variable(self) -> None:
        # The environment must be cleared explicitly. An empty `api_key` falls
        # through to os.getenv (openrouter.py:77), so on a machine that has the
        # key configured -- which is every machine that can actually run a
        # sweep -- this test would construct a *working* client and fail.
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            client = OpenRouterClient(model="qwen/qwen3-32b", api_key="")
            with self.assertRaisesRegex(LLMUnavailable, "OPENROUTER_API_KEY"):
                client.chat(MESSAGES)

    def test_bad_key_is_not_reported_as_an_outage(self) -> None:
        with patch("urllib.request.urlopen", side_effect=http_error(401)):
            with self.assertRaisesRegex(LLMUnavailable, "API key"):
                self.client.chat(MESSAGES)

    def test_out_of_credit_says_so(self) -> None:
        with patch("urllib.request.urlopen", side_effect=http_error(402)):
            with self.assertRaisesRegex(LLMUnavailable, "out of credit"):
                self.client.chat(MESSAGES)

    def test_unknown_model_says_so(self) -> None:
        with patch("urllib.request.urlopen", side_effect=http_error(404)):
            with self.assertRaisesRegex(LLMUnavailable, "model id"):
                self.client.chat(MESSAGES)

    def test_rate_limit_is_retried_and_can_succeed(self) -> None:
        """A single 429 must not end a twelve-model sweep."""

        attempts = [http_error(429), FakeResponse(ok_body())]

        def flaky(*_args, **_kwargs):
            outcome = attempts.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch("urllib.request.urlopen", side_effect=flaky):
            with patch("time.sleep") as slept:  # keep the suite fast
                result = self.client.chat(MESSAGES)

        self.assertEqual(result.text, "Stay under the table.")
        self.assertTrue(slept.called, "a 429 should back off before retrying")
        self.assertEqual(attempts, [], "both responses should have been consumed")

    def test_rate_limit_eventually_gives_up_with_a_clear_message(self) -> None:
        with patch("urllib.request.urlopen", side_effect=http_error(429)):
            with patch("time.sleep"):
                with self.assertRaisesRegex(LLMUnavailable, "rate limit"):
                    self.client.chat(MESSAGES)

    def test_a_client_error_is_not_retried_with_the_same_payload(self) -> None:
        """The retry ladder must not repeat a malformed request verbatim.

        There are exactly two attempts, not one: the second drops the
        `reasoning` parameter, because some models declare reasoning mandatory
        and reject `effort: "none"` with a 400.  That is a different request, not
        a retry of the same one -- the ladder itself still refuses to retry 4xx.
        """

        sent: list[dict] = []

        def counted(request, **_kwargs):
            sent.append(json.loads(request.data.decode("utf-8")))
            raise http_error(400)

        with patch("urllib.request.urlopen", side_effect=counted):
            with self.assertRaises(LLMUnavailable):
                self.client.chat(MESSAGES)

        self.assertEqual(len(sent), 2)
        self.assertIn("reasoning", sent[0])
        self.assertNotIn("reasoning", sent[1])

    def test_an_unreachable_service_is_not_retried_twice_over(self) -> None:
        """The gap that let a sixteen-minute hang ship.

        The reasoning fallback re-sends without the `reasoning` parameter, which
        is right for a model that rejects `effort: "none"` with a 400. It was
        guarded by `if not self.reasoning_effort: raise` -- and the default
        effort is the string "none", which is truthy, so the guard never fired
        and EVERY failure ran the ladder twice.

        On a network that drops packets rather than refusing them that is
        4 x 120s + backoff, doubled: about sixteen minutes of server-side work
        for one child's question, long after Unity gave up at 40s. The endpoint
        is a sync def, so each one holds a worker thread.

        `test_a_client_error_is_not_retried_with_the_same_payload` did not catch
        it: a 400 is not in RETRY_STATUSES, so each ladder exits on its first
        attempt and the doubling is invisible at two sends.
        """

        attempts = []

        def unreachable(*_args, **_kwargs):
            attempts.append(1)
            raise urllib.error.URLError("connection timed out")

        client = OpenRouterClient(
            model="qwen/qwen3-32b", api_key="test-key", max_attempts=3
        )
        with patch("urllib.request.urlopen", side_effect=unreachable):
            with patch("time.sleep"):
                with self.assertRaisesRegex(LLMUnavailable, "unreachable"):
                    client.chat(MESSAGES)

        self.assertEqual(
            len(attempts),
            3,
            "an outage must cost max_attempts, not max_attempts doubled by the "
            "reasoning fallback",
        )

    def test_a_rejected_parameter_still_gets_the_second_chance(self) -> None:
        """The narrowing must not remove the behaviour it was written for."""

        sent: list[dict] = []

        def reject_then_accept(request, **_kwargs):
            payload = json.loads(request.data.decode("utf-8"))
            sent.append(payload)
            if "reasoning" in payload:
                raise http_error(400, "reasoning is required for this model")
            return FakeResponse(ok_body())

        with patch("urllib.request.urlopen", side_effect=reject_then_accept):
            result = self.client.chat(MESSAGES)

        self.assertEqual(result.text, "Stay under the table.")
        self.assertEqual(len(sent), 2)
        self.assertNotIn("reasoning", sent[1])

    def test_reasoning_is_disabled_by_default(self) -> None:
        """Reasoning tokens come out of the same budget as the answer.

        Measured on the real sweep: with reasoning on, DeepSeek V4 Pro answered
        only 19 of 44 questions -- the rest spent the budget thinking, returned
        empty content, and were scored as the pipeline's fallback instead.
        """

        sent: list[dict] = []

        def capture(request, **_kwargs):
            sent.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse(ok_body())

        with patch("urllib.request.urlopen", side_effect=capture):
            self.client.chat(MESSAGES)

        self.assertEqual(sent[0]["reasoning"], {"effort": "none"})
        self.assertEqual(self.client.status["reasoning_effort"], "none")

    def test_empty_content_is_an_error_not_an_empty_answer(self) -> None:
        empty = io.BytesIO(
            json.dumps({"choices": [{"message": {"content": "   "}}]}).encode("utf-8")
        )
        with patch("urllib.request.urlopen", return_value=FakeResponse(empty)):
            with self.assertRaisesRegex(LLMUnavailable, "no answer"):
                self.client.chat(MESSAGES)

    def test_malformed_json_is_reported_as_such(self) -> None:
        junk = io.BytesIO(b"<html>502 Bad Gateway</html>")
        with patch("urllib.request.urlopen", return_value=FakeResponse(junk)):
            with self.assertRaisesRegex(LLMUnavailable, "invalid JSON"):
                self.client.chat(MESSAGES)

    def test_sampling_settings_match_the_ollama_client(self) -> None:
        """A model comparison must not also be a settings comparison."""

        captured = {}

        def capture(request, **_kwargs):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse(ok_body())

        with patch("urllib.request.urlopen", side_effect=capture):
            self.client.chat(MESSAGES)

        self.assertEqual(captured["temperature"], 0.1)
        self.assertEqual(captured["max_tokens"], 128)
        self.assertEqual(captured["messages"], MESSAGES)
        self.assertFalse(captured["stream"])


if __name__ == "__main__":
    unittest.main()
