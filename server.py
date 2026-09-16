"""FastAPI boundary for CALM's deterministic context-aware assistant."""

from __future__ import annotations

from copy import deepcopy
import json
import os
import tempfile
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Literal, NamedTuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from calm_core import (
    CALMAssistant,
    ContextValidationError,
    LLMUnavailable,
    OllamaClient,
    OpenRouterClient,
    RAGChatService,
    UnityScenarioCrosswalk,
)
from calm_core.env_file import load_env_file
from calm_core.question_scope import detect_locale
from calm_core.rag_chat import AUTO_LOCALE
from calm_core.router import FALLBACKS
from calm_core.session_log import SessionLog
from calm_core.speech import (
    MAX_SPEAKABLE_CHARS,
    EdgeSpeechSynthesizer,
    SpeechUnavailable,
)


ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "index.html"
RAG_TEST_PATH = ROOT / "rag_test.html"
SIMULATION_PATH = ROOT / "simulation.html"
STATIC_PATH = ROOT / "static"
# FIRST, before anything reads os.getenv. Every CALM_* setting below is read at
# import time, so a load placed after them is a load that does nothing for them.
#
# It was placed after them. CALM_CORPUS_MODE, CALM_SCHOOL_PROFILE,
# CALM_MAX_AUDIO_BYTES and -- worst -- CALM_UNITY_DRIFT were therefore silently
# unsettable from .env. CALM_UNITY_DRIFT is the documented escape hatch for a
# crosswalk mismatch that otherwise stops the server booting at all, so it was
# broken exactly where a facilitator would reach for it, on the one morning it
# matters. An already-set variable still wins, so the Unity launcher's settings
# and a developer's own key both survive this.
_env_from_file = load_env_file()

CORPUS_MODE = os.getenv("CALM_CORPUS_MODE", "development")
SCHOOL_PROFILE_PATH = os.getenv("CALM_SCHOOL_PROFILE")
MAX_AUDIO_BYTES = int(os.getenv("CALM_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))

assistant = CALMAssistant(
    corpus_mode=CORPUS_MODE,
    school_profile_path=Path(SCHOOL_PROFILE_PATH)
    if SCHOOL_PROFILE_PATH
    else None,
)
unity_crosswalk = UnityScenarioCrosswalk()


def _build_llm_provider():
    """Pick the generation provider. Local unless deliberately told otherwise.

    Defaulting to Ollama is the point: a hosted provider sends the learner's
    question to a third party, so that has to be an explicit act. Selecting on
    "is OPENROUTER_API_KEY present" would make it an accident of the
    environment, which is exactly how a key left over from a benchmark run
    would end up serving children.
    """

    choice = os.getenv("CALM_LLM_PROVIDER", "ollama").strip().lower()
    if choice == "openrouter":
        return OpenRouterClient()
    if choice not in {"", "ollama"}:
        raise RuntimeError(
            f"CALM_LLM_PROVIDER={choice!r} is not a known provider "
            "(expected 'ollama' or 'openrouter')."
        )
    return OllamaClient()


rag_chat = RAGChatService(
    _build_llm_provider(),
    unity_crosswalk,
    repository=assistant.repository,
)
speech = EdgeSpeechSynthesizer()
session_log = SessionLog()

app = FastAPI(
    title="CALM AI Subsystem",
    version="0.3.0",
    description=(
        "Context-aware, deterministic safety routing with curated RAG for "
        "noncritical educational questions."
    ),
)

allowed_origins = [
    item.strip()
    for item in os.getenv(
        "CALM_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,null",
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


class AssistantRequest(BaseModel):
    question: str = Field(default="", max_length=500)
    locale: Literal["en-PH", "fil-PH", "taglish-PH"] = "en-PH"
    context: dict[str, Any]


class RAGChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    task_id: str = Field(min_length=1, max_length=100)
    #: "auto" answers in the language the question was asked in. The
    #: response always reports a concrete locale.
    locale: Literal["en-PH", "fil-PH", "taglish-PH", "auto"] = "en-PH"
    #: Opaque client-side id used only to group one session's events. Optional:
    #: a missing id logs an anonymous event rather than failing a child's
    #: question. Must not be derived from anything identifying.
    session_id: str | None = Field(default=None, max_length=64)
    #: The immediately preceding exchange, supplied by the headset only to make
    #: short follow-ups intelligible. It is used for this request and never
    #: written to CALM's session log.
    previous_question: str | None = Field(default=None, max_length=500)
    previous_response: str | None = Field(default=None, max_length=800)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAKABLE_CHARS)
    locale: Literal["en-PH", "fil-PH", "taglish-PH"] = "en-PH"


Locale = Literal["en-PH", "fil-PH", "taglish-PH"]
QuestionScope = Literal[
    "on_task", "in_hazard_off_task", "cross_hazard", "out_of_scope"
]
CompletionCode = Literal[
    "OK",
    "OK_CROSS_HAZARD",
    "OK_IN_HAZARD_OFF_TASK",
    "OK_GENERAL_QA",
    "DEFERRED_DURING_CRITICAL_TASK",
    "NO_RELEVANT_EVIDENCE",
    "OUTSIDE_DISASTER_SCOPE",
]
EvidenceScope = Literal[
    "task_evidence",
    "task_plus_phase_evidence",
    "asked_hazard_evidence",
    "general_evidence",
    "none",
]


class GenerationInfo(BaseModel):
    elapsed_ms: int
    prompt_tokens: int
    output_tokens: int
    output_normalized: bool
    #: Must be declared here or Pydantic drops it on the way out and the
    #: headset never learns the answer was cut off mid-sentence.
    truncated: bool = False


class ChatResponse(BaseModel):
    """The contract a Unity client binds to.

    The closed value sets below are the point of this model: a client can switch
    on completion_code and question_scope knowing the server cannot silently
    invent a new one. Adding a branch here is a deliberate contract change that
    breaks the schema loudly rather than reaching the headset unannounced.
    """

    response_text: str
    question: str
    locale: Locale
    task_id: str
    scenario_id: str
    scene: str
    hazard: Literal["earthquake", "fire", "typhoon"]
    phase: Literal["before", "during", "after"]
    setting: Literal["home", "school", "outdoor"]
    active_simulation_instruction: str
    mapping_status: str
    scope_constraint: str | None = None
    general_qa: bool = False
    retrieval_mode: Literal["task_scoped", "all_supported_hazards"] = "task_scoped"

    question_scope: QuestionScope
    asked_hazard: Literal["earthquake", "fire", "typhoon"] | None = None
    deferred_question: bool
    completion_code: CompletionCode
    answer_source: Literal[
        "llm", "deterministic_fallback", "grounding_guardrail_fallback"
    ]
    evidence_scope: EvidenceScope

    retrieved_evidence_ids: list[str]
    deviation_evidence_ids: list[str]

    provider: str
    #: None whenever a deterministic branch answered without calling the model.
    model: str | None = None
    llm_used: bool
    grounding_mode: str
    prompt_policy_version: str
    generation: GenerationInfo
    #: Sanitized decision record. Forward this and nothing else to a dashboard;
    #: see docs/EQ_SCHOOL_UNITY_INTEGRATION.md for the deny list it satisfies.
    dashboard_event: dict[str, Any]


class VoiceChatResponse(ChatResponse):
    #: What Whisper heard, so a tester can tell a mishearing from a bad answer.
    transcript: str
    input_mode: Literal["voice"]
    #: The language Whisper decoded the audio in ("en", "tl", ...). Reported so
    #: a locale mismatch is visible: a "tl" transcript answered in "en-PH" means
    #: the child spoke Filipino and was answered in English.
    transcribed_language: str


def _validate_voice_chat_metadata(
    *,
    task_id: str,
    session_id: str | None,
    previous_question: str | None,
    previous_response: str | None,
) -> tuple[str, str | None, str | None, str | None]:
    """Apply the JSON endpoint's bounds before expensive transcription.

    FastAPI's plain ``Form`` annotations do not share ``RAGChatRequest``'s
    Pydantic limits. Without this gate a multipart client could make Whisper do
    work and then send arbitrarily large dialogue metadata into the prompt.
    """

    cleaned_task_id = task_id.strip()
    if not cleaned_task_id:
        raise HTTPException(status_code=422, detail="task_id must not be empty")
    if len(cleaned_task_id) > 100:
        raise HTTPException(
            status_code=422, detail="task_id must be 100 characters or fewer"
        )

    values = {
        "session_id": (session_id, 64),
        "previous_question": (previous_question, 500),
        "previous_response": (previous_response, 800),
    }
    normalized: dict[str, str | None] = {}
    for name, (value, maximum) in values.items():
        cleaned = (value or "").strip() or None
        if cleaned is not None and len(cleaned) > maximum:
            raise HTTPException(
                status_code=422,
                detail=f"{name} must be {maximum} characters or fewer",
            )
        normalized[name] = cleaned
    return (
        cleaned_task_id,
        normalized["session_id"],
        normalized["previous_question"],
        normalized["previous_response"],
    )


@app.get("/")
def prototype_page() -> FileResponse:
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="Prototype page not found")
    return FileResponse(INDEX_PATH)


@app.get("/simulation")
def simulation_page() -> FileResponse:
    """Serve the learner-facing low-poly Unity UI previsualization."""

    if not SIMULATION_PATH.exists():
        raise HTTPException(status_code=404, detail="Simulation page not found")
    return FileResponse(SIMULATION_PATH)


@app.get("/rag")
def rag_test_page() -> FileResponse:
    if not RAG_TEST_PATH.exists():
        raise HTTPException(status_code=404, detail="RAG test page not found")
    return FileResponse(RAG_TEST_PATH)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "corpus": assistant.repository.status,
        "school_config": assistant.school.status,
        "missions": assistant.missions.status,
        "rag_chat": rag_chat.status,
        "speech_model_loaded": _stt_engine is not None,
        "speech_synthesis": speech.status,
        "session_log": session_log.status,
    }


@app.get("/api/v1/unity/tasks")
def list_unity_tasks() -> dict[str, Any]:
    """Return the implemented Unity tasks available to the RAG test client."""

    return {
        "crosswalk_version": unity_crosswalk.data["crosswalk_version"],
        "missions": [
            {
                "scene": mission["scene"],
                "scenario_id": mission["scenario_id"],
                "hazard": mission["hazard"],
                "setting": mission["setting"],
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "phase": task["phase"],
                        "learner_action": task["learner_action"],
                        "instruction": task["active_simulation_instruction"],
                        "mapping_status": task["mapping_status"],
                        "general_qa": bool(task.get("general_qa", False)),
                    }
                    for task in mission["tasks"]
                ],
            }
            for mission in unity_crosswalk.data["missions"]
        ],
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(payload: RAGChatRequest) -> dict[str, Any]:
    """Generate an Ollama answer grounded in one trusted Unity task."""

    try:
        result = rag_chat.answer(
            question=payload.question,
            task_id=payload.task_id,
            locale=payload.locale,
            session_id=payload.session_id,
            previous_question=payload.previous_question,
            previous_response=payload.previous_response,
        )
        # Recorded after the answer exists, so a logging problem can never cost
        # the learner the instruction.
        session_log.record(result["dashboard_event"])
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/api/v1/speak",
    response_class=Response,
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "Spoken answer as MP3 audio.",
        },
        503: {"description": "Synthesis unavailable; the answer text still stands."},
    },
)
def speak(payload: SpeechRequest) -> Response:
    """Speak a reviewed CALM sentence in a Philippine voice.

    Kept separate from /api/v1/chat so a headset can render the answer text
    immediately and fetch audio alongside it, and so a synthesis outage never
    costs the learner their safety instruction.
    """

    try:
        result = speech.speak(payload.text, payload.locale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SpeechUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=result.audio,
        media_type=result.media_type,
        headers={
            "X-CALM-Voice": result.voice,
            "X-CALM-Locale": result.locale,
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/v1/voice-chat", response_model=VoiceChatResponse)
def voice_chat(
    audio_file: UploadFile = File(...),
    task_id: str = Form(...),
    locale: Literal["en-PH", "fil-PH", "taglish-PH", "auto"] = Form("en-PH"),
    session_id: str | None = Form(None),
    previous_question: str | None = Form(None),
    previous_response: str | None = Form(None),
) -> dict[str, Any]:
    """Spoken question in, grounded answer out, for one trusted Unity task.

    The learner's audio is transcribed locally and the temporary file is always
    removed.  Speech is treated exactly like typed text once transcribed: it is
    a question, never an instruction that can redirect the simulation.
    """

    task_id, session_id, previous_question, previous_response = (
        _validate_voice_chat_metadata(
            task_id=task_id,
            session_id=session_id,
            previous_question=previous_question,
            previous_response=previous_response,
        )
    )
    try:
        transcription = _transcribe_upload(audio_file, locale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transcript = transcription.text
    if not transcript.strip():
        raise HTTPException(
            status_code=422, detail="No speech was recognised in the audio"
        )
    # Resolved here rather than inside rag_chat.answer: the pipeline would run
    # detect_locale over the transcript alone, and the transcript is only in the
    # child's own language because the audio was decoded in it. Keeping both
    # halves together is what stops a Filipino question becoming an English one.
    if locale == AUTO_LOCALE:
        locale = resolve_spoken_locale(transcription)
    try:
        result = rag_chat.answer(
            question=transcript,
            task_id=task_id,
            locale=locale,
            session_id=session_id,
            previous_question=previous_question,
            previous_response=previous_response,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["transcript"] = transcript
    result["input_mode"] = "voice"
    result["transcribed_language"] = transcription.language
    # The event records that the question was spoken, never what was said: the
    # transcript sits in the response beside it and the sink's allowlist is what
    # keeps it out of the file.
    result["dashboard_event"]["input_mode"] = "voice"
    result["dashboard_event"]["endpoint"] = "/api/v1/voice-chat"
    # Carried into telemetry so a mishearing is visible as a mishearing. A
    # "tl" here against an "en-PH" answer locale is the signature of the bug
    # this field was added for.
    result["dashboard_event"]["transcribed_language"] = transcription.language
    session_log.record(result["dashboard_event"])
    return result


@app.get("/api/v1/missions")
def list_missions() -> dict[str, Any]:
    """List validated mission contracts available to a Unity client."""

    return {"missions": assistant.missions.summaries}


@app.get("/api/v1/missions/{mission_id}")
def get_mission(mission_id: str) -> dict[str, Any]:
    """Return the contract plus an exact, card-derived verification oracle."""

    contract = assistant.missions.get(mission_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Mission contract not found")
    payload = deepcopy(contract.data)
    verification = payload.get("verification", {})
    verification["oracle_source"] = (
        "reviewed protocol-card language packs and deterministic fallbacks"
    )
    verification["oracle_generated"] = True
    for state_id, expected in verification.get("states", {}).items():
        state = payload["states"][state_id]
        card = assistant.repository.get(state["calm"]["protocol_id"])
        if card is None:
            raise HTTPException(
                status_code=503,
                detail=f"Mission verification card unavailable: {state_id}",
            )
        mode = expected.get("response_mode")
        if mode == "no_route_fallback":
            expected_text = {
                locale: FALLBACKS[locale]["no_route"]
                for locale in sorted(FALLBACKS)
            }
        else:
            expected_text = {
                locale: localized["tts_text"]
                for locale, localized in card["language_pack"].items()
            }
        expected["expected_response_text"] = expected_text
        expected["expected_tts_text"] = deepcopy(expected_text)
        expected["expected_blocked_action_codes"] = list(
            card["deterministic_safety"].get("blocks_action_codes", [])
        )
        expected["expected_protocol_revision"] = card["revision"]
    return payload


@app.post("/api/v1/respond")
def respond(payload: AssistantRequest) -> dict[str, Any]:
    """Primary Unity boundary: trusted state and learner question stay separate."""

    try:
        result = assistant.respond(
            question=payload.question,
            context=payload.context,
            locale=payload.locale,
        )
        event = dict(result.get("dashboard_event", {}))
        event["endpoint"] = "/api/v1/respond"
        # The router names it completion_or_error_code; the sink's allowlist
        # speaks completion_code. Same concept, one vocabulary in the log.
        if "completion_or_error_code" in event:
            event["completion_code"] = event.pop("completion_or_error_code")
        event["decision_trace"] = result.get("decision_trace")
        session_log.record(event)
        return result
    except ContextValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


_stt_engine: Any | None = None
_stt_lock = Lock()
_transcribe_lock = Lock()


@app.on_event("startup")
def _warm_speech_model() -> None:
    """Load Whisper in the background so no child pays for it.

    Measured on this project's CPU configuration: loading the model costs ~5.4 s
    and transcribing a 4-second question ~5 s. Loaded lazily, the *first* spoken
    question of a session therefore took about twice as long as every one after
    it -- and the first question of a session is the one a nine-year-old is
    least willing to wait through, and the one a facilitator judges the system
    on.

    A daemon thread, so the server still answers /health immediately and a
    machine with no faster-whisper installed still starts: the failure surfaces
    on the first real voice request exactly as it did before.

    Fires on ASGI startup, not at import, so the test suite (which drives the
    app through ASGITransport without lifespan) never loads a speech model.
    """

    def warm() -> None:
        try:
            _get_stt_engine()
        except Exception as error:  # noqa: BLE001 - never block startup
            print(f"CALM: speech model not pre-warmed ({error})", flush=True)

    Thread(target=warm, name="calm-warm-stt", daemon=True).start()


def _get_stt_engine() -> Any:
    """Load Whisper, warmed at startup and lazily thereafter."""

    global _stt_engine
    if _stt_engine is not None:
        return _stt_engine
    with _stt_lock:
        if _stt_engine is not None:
            return _stt_engine
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Voice transcription is unavailable; install faster-whisper"
            ) from exc

        # Transcription is eight times faster on the GPU and the model fits
        # alongside the language model, but a machine without CUDA must still
        # be able to run a lesson, so the GPU is attempted and not required.
        configured_device = os.getenv("CALM_WHISPER_DEVICE", "auto")
        device = configured_device
        if device == "auto":
            device = "cuda" if _cuda_is_usable() else "cpu"
        configured_compute_type = os.getenv("CALM_WHISPER_COMPUTE_TYPE")
        compute_type = configured_compute_type or (
            "int8" if device == "cpu" else "float16"
        )
        # "base" mis-hears Filipino badly.  "small" is the smallest size that
        # transcribes it usefully, and it still fits alongside the LLM.
        model_name = os.getenv("CALM_WHISPER_MODEL", "small")
        try:
            _stt_engine = WhisperModel(
                model_name, device=device, compute_type=compute_type
            )
        except Exception as exc:
            # A larger model is fetched on first use.  On a machine that is
            # offline, or in a classroom with no network, refusing to transcribe
            # at all would be worse than transcribing less accurately, so fall
            # back to whatever smaller model is already cached.
            if model_name == STT_FALLBACK_MODEL:
                raise RuntimeError(
                    f"Voice transcription is unavailable: {exc}"
                ) from exc
            try:
                _stt_engine = WhisperModel(
                    STT_FALLBACK_MODEL, device=device, compute_type=compute_type
                )
            except Exception as fallback_exc:
                # Auto mode means "use the fastest working device", not "fail
                # if CUDA was detectable but the requested model did not fit".
                # A 4 GB laptop GPU can pass the tiny-model probe and still run
                # out of memory loading `small` beside Ollama. Retry on CPU.
                if configured_device != "auto" or device == "cpu":
                    raise RuntimeError(
                        f"Voice transcription is unavailable: {fallback_exc}"
                    ) from fallback_exc
                cpu_compute = configured_compute_type or "int8"
                try:
                    _stt_engine = WhisperModel(
                        model_name, device="cpu", compute_type=cpu_compute
                    )
                except Exception:
                    try:
                        _stt_engine = WhisperModel(
                            STT_FALLBACK_MODEL,
                            device="cpu",
                            compute_type=cpu_compute,
                        )
                    except Exception as cpu_exc:
                        raise RuntimeError(
                            f"Voice transcription is unavailable: {cpu_exc}"
                        ) from cpu_exc
        return _stt_engine


#: Always shipped with faster-whisper's first run, so it is the size that
#: can be relied on to already exist on an offline machine.
STT_FALLBACK_MODEL = "base"


def _cuda_is_usable() -> bool:
    """True when a CUDA transcription model can actually be built.

    Reporting a GPU is not the same as being able to use one: ctranslate2 needs
    cuDNN beside the driver, and a missing library surfaces only when a model is
    constructed.  Probing with the smallest model is cheap next to discovering
    this on a learner's first spoken question.
    """

    try:
        from faster_whisper import WhisperModel

        WhisperModel("tiny", device="cuda", compute_type="float16")
        return True
    except Exception:
        return False

ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}


def _transcribe_upload(audio_file: UploadFile, locale: str = "en-PH") -> Transcription:
    """Spool an upload to disk, transcribe locally, and always delete it.

    Learner audio is the most sensitive thing this system touches, so it lives
    only as long as the transcription call and never leaves the machine.
    """

    supplied = Path(audio_file.filename or "audio.wav").suffix.lower()
    suffix = supplied if supplied in ALLOWED_AUDIO_SUFFIXES else ".audio"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="calm_audio_", suffix=suffix, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            written = 0
            while chunk := audio_file.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_AUDIO_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio upload exceeds the configured size limit",
                    )
                temporary.write(chunk)
        return _transcribe(temporary_path, locale)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


#: Whisper's language codes for the locales CALM speaks.  Taglish is code-mixed
#: with no code of its own; forcing Tagalog there transcribes the Filipino words
#: correctly and leaves the borrowed English ones intelligible, which is far
#: better than letting detection pick English and render the Filipino as noise.
WHISPER_LANGUAGE = {"en-PH": "en", "fil-PH": "tl", "taglish-PH": "tl"}
#: Anchors the decoder in the domain, which measurably reduces invented text on
#: short utterances.
WHISPER_PROMPT = {
    "en": "A Grade 4 pupil asks about earthquake, fire, or typhoon safety.",
    "tl": "Nagtatanong ang bata tungkol sa lindol, sunog, o bagyo at kaligtasan.",
}
#: What Whisper may call Tagalog.  It has no code for Taglish, so code-mixed
#: speech comes back as one of these or as "en" depending on the mix.
TAGALOG_WHISPER_CODES = {"tl", "fil", "tgl"}


class Transcription(NamedTuple):
    """A transcript plus what Whisper believed it was listening to.

    The language is carried out of this function rather than discarded because
    it is the only evidence of a mishearing that the rest of the request can
    see.  Without it, Filipino speech rendered as English is indistinguishable
    from a child who spoke English.
    """

    text: str
    language: str
    language_probability: float


def _transcribe(path: Path, locale: str = "en-PH") -> Transcription:
    """Transcribe locally, telling Whisper which language to expect.

    Without an explicit language Whisper auto-detects, and on a short Filipino
    utterance it frequently guesses English and then invents a fluent English
    sentence that was never spoken.  A wrong transcript is worse than none: it
    reaches the router as a confident question.

    ``AUTO_LOCALE`` is the deliberate exception and the reason this function
    reports the detected language back.  Unity sends ``auto`` on every spoken
    question (``CalmClient.Locale``), and until 2026-09-17 ``auto`` fell through
    a ``.get(locale, "en")`` default -- so *every* spoken Filipino question in
    the product was transcribed in forced-English mode, producing exactly the
    invented English sentence this docstring warns about.  The failure was
    silent: ``detect_locale`` then read the invention, reported ``en-PH``, and
    nothing recorded that the child had spoken Filipino.
    """

    # Resolved before the engine is touched, so an unsupported locale costs
    # nothing and cannot be masked by a model-loading failure.
    if locale == AUTO_LOCALE:
        # No forced language and no domain prompt: the prompt is written in one
        # language and would bias detection toward it, which is the whole thing
        # being avoided here.
        language = None
    else:
        try:
            language = WHISPER_LANGUAGE[locale]
        except KeyError:
            # Loud, not a default. A silent fallback to English here is what the
            # bug above was made of.
            raise ValueError(
                f"unsupported locale for transcription: {locale!r}; "
                f"expected one of {sorted(WHISPER_LANGUAGE)} or {AUTO_LOCALE!r}"
            ) from None

    model = _get_stt_engine()
    # A single faster-whisper model is shared by all FastAPI worker threads.
    # Serializing inference avoids overlapping GPU buffers and protects the
    # generator-backed segment stream from concurrent use.
    with _transcribe_lock:
        segments, info = model.transcribe(
            str(path),
            beam_size=5,
            language=language,
            initial_prompt=WHISPER_PROMPT.get(language) if language else None,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        text = " ".join(segment.text for segment in segments).strip()

    detected = getattr(info, "language", None) or language or "en"
    probability = float(getattr(info, "language_probability", 0.0) or 0.0)
    return Transcription(text=text, language=detected, language_probability=probability)


def resolve_spoken_locale(transcription: Transcription) -> str:
    """Pick the CALM locale for a transcript Whisper detected the language of.

    Whisper can tell Tagalog from English; it has no concept of Taglish. So the
    audio decides whether Filipino was spoken at all, and the *text* decides
    between Filipino and Taglish -- which is precisely what ``detect_locale``
    was written to do, from the question's Filipino function words.

    Code-mixed speech is the case that needs both: a mostly-English Taglish
    sentence is routinely detected as ``en``, so an English detection is not
    allowed to overrule Filipino function words actually present in the text.
    """

    from_text = detect_locale(transcription.text)
    if transcription.language in TAGALOG_WHISPER_CODES:
        # Heard as Tagalog. If the text reads as pure English anyway (a very
        # short or noisy utterance), trust the audio over the word list.
        return from_text if from_text != "en-PH" else "fil-PH"
    return from_text


@app.post("/api/process-voice")
def process_voice_payload(
    audio_file: UploadFile = File(...),
    vr_context_json: str = Form(...),
    locale: Literal["en-PH", "fil-PH", "taglish-PH"] = Form("en-PH"),
    active_module: str | None = Form(None),
) -> dict[str, Any]:
    """Compatibility voice boundary; it still requires the complete VR state."""

    try:
        context = json.loads(vr_context_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail="vr_context_json must be valid JSON"
        ) from exc
    if not isinstance(context, dict):
        raise HTTPException(
            status_code=422, detail="vr_context_json must contain an object"
        )
    if active_module and context.get("hazard") != active_module:
        raise HTTPException(
            status_code=409,
            detail=(
                "active_module conflicts with trusted context.hazard; the "
                "trusted context must win"
            ),
        )

    allowed_suffixes = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}
    supplied_suffix = Path(audio_file.filename or "audio.wav").suffix.lower()
    suffix = supplied_suffix if supplied_suffix in allowed_suffixes else ".audio"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="calm_audio_", suffix=suffix, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            written = 0
            while chunk := audio_file.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_AUDIO_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio upload exceeds the configured size limit",
                    )
                temporary.write(chunk)
        # This endpoint's locale is always concrete (its Literal excludes
        # "auto"), so the detected language carries no extra information here.
        transcription = _transcribe(temporary_path, locale).text
        result = assistant.respond(
            question=transcription,
            context=context,
            locale=locale,
        )
        result["transcription"] = transcription
        result["response"] = result["response_text"]
        result["transcription_retained"] = False
        return result
    except ContextValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("CALM_BIND_HOST", "127.0.0.1"),
        port=int(os.getenv("CALM_PORT", "8010")),
    )
