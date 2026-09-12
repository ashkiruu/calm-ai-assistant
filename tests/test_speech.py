from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from calm_core.speech import (
    MAX_SPEAKABLE_CHARS,
    VOICES,
    EdgeSpeechSynthesizer,
    SpeechUnavailable,
)


class VoiceSelectionTests(unittest.TestCase):
    """The voice is a learning-design decision, so pin it like one."""

    def test_every_supported_locale_has_a_philippine_voice(self) -> None:
        self.assertEqual(set(VOICES), {"en-PH", "fil-PH", "taglish-PH"})
        for locale, voice in VOICES.items():
            with self.subTest(locale=locale):
                self.assertTrue(
                    voice.startswith(("en-PH-", "fil-PH-")),
                    f"{locale} uses a non-Philippine voice: {voice}",
                )

    def test_english_uses_a_philippine_accent(self) -> None:
        """A foreign accent is harder for Grade 4 Filipino learners to follow."""

        self.assertEqual(VOICES["en-PH"], "en-PH-RosaNeural")

    def test_taglish_reuses_the_filipino_voice(self) -> None:
        self.assertEqual(VOICES["taglish-PH"], VOICES["fil-PH"])

    def test_every_voice_is_philippine(self) -> None:
        """No single voice covers both Philippine English and Filipino, so the
        persona is held steady by nationality and gender rather than by reusing
        one voice. This asserts the half that can be enforced in code."""

        self.assertEqual(
            {v.rsplit("-", 1)[0] for v in VOICES.values()},
            {"en-PH", "fil-PH"},
        )

    def test_unsupported_locale_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported locale"):
            EdgeSpeechSynthesizer().voice_for("en-US")


class SynthesisContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.synth = EdgeSpeechSynthesizer()

    def test_empty_text_is_rejected_before_any_network_call(self) -> None:
        with patch.object(EdgeSpeechSynthesizer, "_synthesize") as synthesize:
            with self.assertRaisesRegex(ValueError, "must not be empty"):
                self.synth.speak("   ", "en-PH")
        synthesize.assert_not_called()

    def test_overlong_text_is_rejected_before_any_network_call(self) -> None:
        with patch.object(EdgeSpeechSynthesizer, "_synthesize") as synthesize:
            with self.assertRaisesRegex(ValueError, "characters or fewer"):
                self.synth.speak("a" * (MAX_SPEAKABLE_CHARS + 1), "en-PH")
        synthesize.assert_not_called()

    def test_successful_synthesis_reports_the_voice_used(self) -> None:
        async def fake(self_, text, voice):
            return b"ID3fake-audio"

        with patch.object(EdgeSpeechSynthesizer, "_synthesize", fake):
            result = self.synth.speak("Stay under the table.", "fil-PH")

        self.assertEqual(result.voice, "fil-PH-BlessicaNeural")
        self.assertEqual(result.locale, "fil-PH")
        self.assertEqual(result.media_type, "audio/mpeg")
        self.assertEqual(result.byte_count, len(b"ID3fake-audio"))

    def test_silent_response_is_an_error_not_an_empty_file(self) -> None:
        """A zero-byte MP3 would play as silence and look like a working answer."""

        async def fake(self_, text, voice):
            return b""

        with patch.object(EdgeSpeechSynthesizer, "_synthesize", fake):
            with self.assertRaisesRegex(SpeechUnavailable, "no audio"):
                self.synth.speak("Stay under the table.", "en-PH")

    def test_network_failure_becomes_a_controlled_error(self) -> None:
        async def fake(self_, text, voice):
            raise OSError("no route to host")

        with patch.object(EdgeSpeechSynthesizer, "_synthesize", fake):
            with self.assertRaises(SpeechUnavailable):
                self.synth.speak("Stay under the table.", "en-PH")

    def test_synthesis_works_from_inside_a_running_event_loop(self) -> None:
        """asyncio.run() raises inside a loop, which any async caller would hit."""

        async def fake(self_, text, voice):
            return b"ID3fake-audio"

        async def call_from_async():
            return self.synth.speak("Stay under the table.", "en-PH")

        with patch.object(EdgeSpeechSynthesizer, "_synthesize", fake):
            result = asyncio.run(call_from_async())

        self.assertEqual(result.byte_count, len(b"ID3fake-audio"))

    def test_status_declares_the_privacy_boundary(self) -> None:
        """The write-up depends on this claim, so assert it rather than trust it."""

        status = self.synth.status
        self.assertFalse(status["sends_learner_audio"])
        self.assertTrue(status["network_required"])
        self.assertEqual(status["provider"], "edge-tts")


if __name__ == "__main__":
    unittest.main()
