"""The spoken question must be decoded in the language the child spoke.

This is the regression these tests exist for, and it ran in production:

    WHISPER_LANGUAGE = {"en-PH": "en", "fil-PH": "tl", "taglish-PH": "tl"}
    language = WHISPER_LANGUAGE.get(locale, "en")     # locale == "auto"

Unity sends ``locale="auto"`` on every spoken question, ``"auto"`` is not a key,
so every Filipino utterance in the product was decoded in forced-English mode --
which ``_transcribe``'s own docstring says makes Whisper "invent a fluent
English sentence that was never spoken". The answer then came back in English
and nothing anywhere recorded that the child had spoken Filipino.

Nothing caught it because the whole path is silent: no exception, no warning, a
plausible transcript, and a perfectly good answer to a question nobody asked.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import httpx

import server
from server import Transcription, resolve_spoken_locale


def heard(text: str, language: str, probability: float = 0.99) -> Transcription:
    return Transcription(text=text, language=language, language_probability=probability)


class TranscriptionLanguageTests(unittest.TestCase):
    """`_transcribe` must never quietly pick a language."""

    def _auto(self, scores: list[tuple[str, float]]):
        with patch.object(server, "_get_stt_engine") as engine, patch(
            "faster_whisper.decode_audio", return_value="decoded-audio"
        ):
            engine.return_value.detect_language.return_value = (
                scores[0][0],
                scores[0][1],
                scores,
            )
            engine.return_value.transcribe.return_value = ([], _Info("zz", 0.1))
            result = server._transcribe(server.Path("x.wav"), server.AUTO_LOCALE)
        return engine, result

    def test_auto_does_not_force_english(self) -> None:
        """The exact bug. `auto` must detect -- here Tagalog wins, so Tagalog."""

        engine, result = self._auto([("tl", 0.7), ("en", 0.2), ("ms", 0.1)])

        _, kwargs = engine.return_value.transcribe.call_args
        self.assertEqual(kwargs["language"], "tl")
        self.assertEqual(result.language, "tl")

    def test_auto_chooses_only_between_english_and_tagalog(self) -> None:
        """Unrestricted detection picked Malay for accented English and then
        transcribed the question INTO Malay ("Apa yang berlaku?")."""

        engine, result = self._auto([("ms", 0.6), ("en", 0.3), ("tl", 0.1)])

        _, kwargs = engine.return_value.transcribe.call_args
        self.assertEqual(kwargs["language"], "en")
        self.assertIsNotNone(kwargs["initial_prompt"])
        self.assertEqual(result.language, "en")
        self.assertAlmostEqual(result.language_probability, 0.3)

    def test_auto_survives_audio_with_no_speech(self) -> None:
        """faster-whisper 1.1.0's VAD path raises on silence; score raw audio."""

        with patch.object(server, "_get_stt_engine") as engine, patch(
            "faster_whisper.decode_audio", return_value="decoded-audio"
        ):
            engine.return_value.detect_language.side_effect = [
                ValueError("need at least one array to concatenate"),
                ("en", 0.5, [("en", 0.5), ("tl", 0.2)]),
            ]
            engine.return_value.transcribe.return_value = ([], _Info())
            result = server._transcribe(server.Path("x.wav"), server.AUTO_LOCALE)

        self.assertEqual(result.language, "en")
        self.assertEqual(result.text, "")

    def test_an_explicit_locale_still_pins_its_language(self) -> None:
        """The non-auto path is unchanged; forcing is right when we were told."""

        for locale, expected in (("fil-PH", "tl"), ("taglish-PH", "tl"), ("en-PH", "en")):
            with self.subTest(locale=locale):
                with patch.object(server, "_get_stt_engine") as engine:
                    engine.return_value.transcribe.return_value = ([], _Info(expected))
                    server._transcribe(server.Path("x.wav"), locale)

                _, kwargs = engine.return_value.transcribe.call_args
                self.assertEqual(kwargs["language"], expected)
                self.assertIsNotNone(kwargs["initial_prompt"])

    def test_an_unknown_locale_raises_instead_of_defaulting(self) -> None:
        """A `.get(locale, "en")` default is what the bug was made of."""

        with patch.object(server, "_get_stt_engine") as engine:
            with self.assertRaisesRegex(ValueError, "unsupported locale"):
                server._transcribe(server.Path("x.wav"), "es-ES")

            engine.assert_not_called()  # and it costs nothing to reject


class ResolveSpokenLocaleTests(unittest.TestCase):
    """Whisper decides whether Filipino was spoken; the text decides Taglish."""

    def test_filipino_audio_gives_a_filipino_locale(self) -> None:
        self.assertEqual(
            resolve_spoken_locale(heard("Ano ang dapat kong gawin?", "tl")), "fil-PH"
        )

    def test_english_audio_gives_english(self) -> None:
        self.assertEqual(
            resolve_spoken_locale(heard("What should I do now?", "en")), "en-PH"
        )

    def test_code_mixed_speech_detected_as_english_is_still_taglish(self) -> None:
        """The case that needs both signals.

        A code-mixed sentence is routinely detected as `en`, so an English
        detection must not overrule Filipino function words plainly in the text.

        The example is `detect_locale`'s own: it keys on English *function*
        words, so "Paano kung may lindol habang nasa school?" is fil-PH despite
        the borrowed "school" -- a content word carries no weight there.
        """

        self.assertEqual(
            resolve_spoken_locale(heard("What if may lindol?", "en")), "taglish-PH"
        )

    def test_filipino_with_only_a_borrowed_content_word_stays_filipino(self) -> None:
        """Pins the distinction above so it reads as intent, not an accident."""

        self.assertEqual(
            resolve_spoken_locale(heard("Paano kung may lindol habang nasa school?", "en")),
            "fil-PH",
        )

    def test_tagalog_audio_transcribed_as_english_words_trusts_the_audio(self) -> None:
        """A short or noisy utterance heard as Tagalog is not answered in English."""

        self.assertEqual(resolve_spoken_locale(heard("Help", "tl")), "fil-PH")

    def test_english_sentence_heard_as_tagalog_is_answered_in_english(self) -> None:
        """Measured: accented English detected as `tl` at 0.55-0.80, transcribed
        correctly word for word, and then answered wholly in Filipino."""

        for text in ("How long do I stay here?", "What do I do next?"):
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_spoken_locale(heard(text, "tl", 0.6)), "en-PH"
                )

    def test_every_tagalog_code_whisper_might_emit_is_recognised(self) -> None:
        for code in ("tl", "fil", "tgl"):
            with self.subTest(code=code):
                self.assertNotEqual(resolve_spoken_locale(heard("Tulong", code)), "en-PH")


class SpokenQuestionEndToEndTests(unittest.TestCase):
    """Through the real HTTP boundary, with only Whisper stubbed.

    The unit tests above prove each half; this proves they are actually wired
    together, which is where the original bug lived -- both halves were fine and
    `auto` simply never reached either of them.
    """

    def post_voice(self, transcription: Transcription):
        async def exercise():
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(
                    "/api/v1/voice-chat",
                    files={"audio_file": ("q.wav", b"RIFFfake", "audio/wav")},
                    data={"task_id": "eq_home_d1_dch", "locale": "auto"},
                )

        with patch.object(server, "_transcribe_upload", return_value=transcription):
            return asyncio.run(exercise())

    def test_a_spoken_filipino_question_is_not_answered_in_english(self) -> None:
        response = self.post_voice(heard("Ano ang dapat kong gawin?", "tl"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["locale"], "fil-PH")
        self.assertEqual(body["transcribed_language"], "tl")

    def test_a_spoken_english_question_is_unaffected(self) -> None:
        response = self.post_voice(heard("What should I do now?", "en"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["locale"], "en-PH")

    def test_the_heard_language_reaches_telemetry(self) -> None:
        """A mishearing has to be visible as one, not inferred from a bad answer."""

        recorded: list[dict] = []
        with patch.object(server.session_log, "record", recorded.append):
            self.post_voice(heard("Ano ang dapat kong gawin?", "tl"))

        self.assertTrue(recorded, "the voice turn should be logged")
        self.assertEqual(recorded[-1]["transcribed_language"], "tl")

    def test_the_heard_language_survives_the_log_allowlist(self) -> None:
        """The test above stubs `record`, so it never saw the sink's allowlist
        drop this field -- which it did, silently, until 2026-09-24."""

        import tempfile

        from calm_core.session_log import SessionLog

        with tempfile.TemporaryDirectory() as directory:
            sink = SessionLog(server.Path(directory) / "sessions.jsonl")
            sink.record(
                {
                    "endpoint": "/api/v1/voice-chat",
                    "transcribed_language": "tl",
                    "question": "Ano ang dapat kong gawin?",
                }
            )
            written = (server.Path(directory) / "sessions.jsonl").read_text(
                encoding="utf-8"
            )

        self.assertIn('"transcribed_language": "tl"', written.replace('":"', '": "'))
        self.assertNotIn("Ano ang dapat", written)


class _Info:
    """Stand-in for faster-whisper's TranscriptionInfo."""

    def __init__(self, language: str = "en", probability: float = 0.99) -> None:
        self.language = language
        self.language_probability = probability


if __name__ == "__main__":
    unittest.main()
