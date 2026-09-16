"""Speak a reviewed CALM answer in a Filipino voice.

Voice selection is part of the learning design, not a detail.  The learners are
Grade 4 children in the Philippines, so an assistant that speaks to them in a
foreign accent is harder to follow and less credible.

    en-PH       Rosa      Philippine-accented English
    fil-PH      Blessica  Filipino
    taglish-PH  Blessica  Filipino, which carries mixed Taglish text acceptably

No single voice speaks both Philippine English and Filipino, so switching
locale necessarily switches voice.  Both are Philippine and female to keep that
change as small as it can be, but a learner who switches language mid-session
will hear a different speaker; only the accent and register stay constant.

Privacy boundary: only text CALM itself authored is ever sent for synthesis.
Learner audio is transcribed locally and never leaves the machine.

That is the whole claim now.  This docstring used to add "and learner questions"
and call synthesis "the one networked step in the pipeline"; both stopped being
true when a hosted generation provider was added (`calm_core/openrouter.py`),
and neither statement was covered by a test, so nothing caught the drift.  Where
a question actually goes is reported per provider as `local_only` in
`LLMProvider.status`, which reaches `/health` -- read that rather than trusting
prose here.  Synthesis remains optional and its failure remains non-fatal.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any


#: Philippine neural voices, chosen female for a single consistent persona.
VOICES = {
    "en-PH": "en-PH-RosaNeural",
    "fil-PH": "fil-PH-BlessicaNeural",
    "taglish-PH": "fil-PH-BlessicaNeural",
}
#: Slightly slowed: these are safety instructions for nine-year-olds, and the
#: default neural rate is pitched at adult listeners.
DEFAULT_RATE = "-10%"
MAX_SPEAKABLE_CHARS = 600


class SpeechUnavailable(RuntimeError):
    """Raised when synthesis cannot be produced, for any reason."""


@dataclass(frozen=True)
class SpeechResult:
    audio: bytes
    voice: str
    locale: str
    rate: str
    media_type: str = "audio/mpeg"

    @property
    def byte_count(self) -> int:
        return len(self.audio)


class EdgeSpeechSynthesizer:
    """Synthesize reviewed answer text using Philippine neural voices.

    The import is deferred to call time so the server still starts, and the
    text pipeline still works, on a machine where the dependency is absent.
    """

    provider = "edge-tts"

    def __init__(
        self, *, rate: str = DEFAULT_RATE, timeout_seconds: float = 20.0
    ) -> None:
        self.rate = rate
        self.timeout_seconds = timeout_seconds

    @property
    def status(self) -> dict[str, Any]:
        try:
            import edge_tts  # noqa: F401

            available = True
            detail = None
        except ImportError as error:
            available = False
            detail = str(error)
        return {
            "provider": self.provider,
            "available": available,
            "detail": detail,
            "voices": dict(VOICES),
            "rate": self.rate,
            "network_required": True,
            "sends_learner_audio": False,
        }

    def voice_for(self, locale: str) -> str:
        try:
            return VOICES[locale]
        except KeyError:
            raise ValueError(f"unsupported locale: {locale}") from None

    async def _synthesize(self, text: str, voice: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate=self.rate)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.extend(chunk["data"])
        return bytes(chunks)

    def speak(self, text: str, locale: str = "en-PH") -> SpeechResult:
        cleaned = " ".join(text.split())
        if not cleaned:
            raise ValueError("text must not be empty")
        if len(cleaned) > MAX_SPEAKABLE_CHARS:
            raise ValueError(
                f"text must be {MAX_SPEAKABLE_CHARS} characters or fewer"
            )
        voice = self.voice_for(locale)

        try:
            import edge_tts  # noqa: F401
        except ImportError as error:
            raise SpeechUnavailable(
                "Speech synthesis needs the edge-tts package. "
                "Install it with: pip install edge-tts"
            ) from error

        def run() -> bytes:
            return asyncio.run(
                asyncio.wait_for(
                    self._synthesize(cleaned, voice), self.timeout_seconds
                )
            )

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                audio = run()
            else:
                # Already inside an event loop, where asyncio.run() raises.  A
                # worker thread keeps this callable from async code without
                # forcing every caller to be async.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    audio = pool.submit(run).result(self.timeout_seconds + 5)
        except asyncio.TimeoutError as error:
            raise SpeechUnavailable(
                f"Speech synthesis timed out after {self.timeout_seconds}s."
            ) from error
        except Exception as error:  # network, service, or codec failure
            raise SpeechUnavailable(f"Speech synthesis failed: {error}") from error

        if not audio:
            raise SpeechUnavailable("Speech synthesis returned no audio.")
        return SpeechResult(audio=audio, voice=voice, locale=locale, rate=self.rate)


__all__ = [
    "DEFAULT_RATE",
    "EdgeSpeechSynthesizer",
    "MAX_SPEAKABLE_CHARS",
    "SpeechResult",
    "SpeechUnavailable",
    "VOICES",
]
