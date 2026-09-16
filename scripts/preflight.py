"""Go / no-go check before a live CALM session. Exits non-zero when it is no-go.

**Why `/health` is not this.** `/health` reports *configuration*, and says "ok"
regardless:

- `"status": "ok"` is a literal (`server.py`), true on an air-gapped laptop.
- `speech_synthesis.available` reflects only whether `import edge_tts` worked,
  not whether Microsoft is reachable.
- `api_key_configured` means "a non-empty string exists", not "the key works" or
  "the account has credit".

So the documented verification step -- curl /health -- passes on a laptop that
cannot answer a single question. This actually calls the model and actually
synthesises speech, because the failures that matter are all failures of things
that are configured correctly and unreachable anyway.

It is deliberately NOT an endpoint: it makes real upstream calls and takes
seconds, while `/health` must stay instant for the headset's own 10s probe.

    python scripts/preflight.py
    python scripts/preflight.py --expect-lan     # also check the sideload config

Every check prints PASS / WARN / FAIL. FAIL means a child will hit it.
WARN means the session runs degraded, which is a decision, not a surprise.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Before anything reads os.getenv, exactly as server.py does.
from calm_core.env_file import load_env_file  # noqa: E402

load_env_file()

from calm_core.llm import LLMUnavailable  # noqa: E402
from calm_core.speech import EdgeSpeechSynthesizer, SpeechUnavailable  # noqa: E402
from calm_core.unity_crosswalk import (  # noqa: E402
    DEFAULT_CARDS,
    DEFAULT_CROSSWALK,
    validate_crosswalk,
)

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
#: Short on purpose. A preflight that takes as long as a broken request is one
#: nobody runs on the morning they need it.
PROBE_TIMEOUT_SECONDS = 10.0


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, verdict: str, name: str, detail: str = "") -> None:
        self.rows.append((verdict, name, detail))
        marker = {PASS: "  OK  ", WARN: " WARN ", FAIL: " FAIL "}[verdict]
        print(f"[{marker}] {name}" + (f"\n          {detail}" if detail else ""))

    @property
    def failed(self) -> bool:
        return any(verdict == FAIL for verdict, _, _ in self.rows)

    @property
    def warned(self) -> bool:
        return any(verdict == WARN for verdict, _, _ in self.rows)


def check_crosswalk(report: Report) -> None:
    """The one failure that stops the server booting at all."""

    result = validate_crosswalk(DEFAULT_CROSSWALK, DEFAULT_CARDS, None)
    if result["status"] == "PASS" and not result["errors"]:
        report.add(
            PASS,
            "Unity crosswalk",
            f"{result['mission_count']} missions, {result['task_count']} tasks, "
            f"{result['referenced_protocol_count']} cards",
        )
        return
    report.add(
        FAIL,
        "Unity crosswalk",
        "the server will refuse to start. "
        + "; ".join(result["errors"][:3])
        + "\n          Freeze MissionLibrary.cs before a session.",
    )


def check_corpus(report: Report, assistant) -> None:
    status = assistant.repository.status
    eligible = status.get("eligible_card_count", 0)
    if eligible > 0:
        report.add(
            PASS,
            "Protocol corpus",
            f"{eligible}/{status.get('total_card_count')} cards eligible "
            f"(mode: {status.get('mode')})",
        )
    else:
        report.add(
            FAIL,
            "Protocol corpus",
            "zero eligible cards -- every answer will be 'no approved answer'.",
        )


def check_model(report: Report, provider) -> None:
    """Actually call the model. Nothing else in the project does this."""

    info = provider.status
    label = f"{info.get('provider')} / {info.get('model')}"
    if info.get("provider") == "openrouter" and not info.get("api_key_configured"):
        report.add(FAIL, f"Model reachable ({label})", "OPENROUTER_API_KEY is not set.")
        return

    started = time.perf_counter()
    try:
        result = provider.chat(
            [
                {"role": "system", "content": "Reply with one short word."},
                {"role": "user", "content": "Say ready."},
            ]
        )
    except LLMUnavailable as error:
        report.add(
            WARN,
            f"Model reachable ({label})",
            f"{error}\n          Session runs DEGRADED: every answer becomes reviewed "
            "deterministic text. Safe and correct, but flat, and nothing tells the "
            "learner or you that it happened.",
        )
        return
    except Exception as error:  # noqa: BLE001 - a preflight must not itself crash
        report.add(FAIL, f"Model reachable ({label})", f"unexpected: {error!r}")
        return

    elapsed = round((time.perf_counter() - started) * 1000)
    if not (result.text or "").strip():
        report.add(WARN, f"Model reachable ({label})", "answered with empty text.")
        return
    report.add(PASS, f"Model reachable ({label})", f"{elapsed} ms")


def check_speech(report: Report) -> None:
    """Actually synthesise. `available` only means the package imported."""

    synth = EdgeSpeechSynthesizer()
    status = synth.status
    if not status.get("available"):
        report.add(
            FAIL,
            "Voice (edge-tts)",
            f"{status.get('detail')} -- KALMA will be silent for the whole session.",
        )
        return
    try:
        spoken = synth.speak("Handa na ako.", "fil-PH")
    except SpeechUnavailable as error:
        report.add(
            WARN,
            "Voice (edge-tts)",
            f"{error}\n          Session runs DEGRADED: KALMA answers in SILENT "
            "SUBTITLES. edge-tts needs the public internet, not just the LAN, and "
            "there is no local fallback.",
        )
        return
    except Exception as error:  # noqa: BLE001
        report.add(FAIL, "Voice (edge-tts)", f"unexpected: {error!r}")
        return

    if spoken.byte_count <= 0:
        report.add(WARN, "Voice (edge-tts)", "returned no audio.")
        return
    report.add(PASS, "Voice (edge-tts)", f"{spoken.byte_count} bytes synthesised")


def check_speech_model(report: Report) -> None:
    """Whisper must be cached locally; the first load is a download."""

    try:
        import server  # noqa: PLC0415 - imported late; it builds the whole app
    except Exception as error:  # noqa: BLE001
        report.add(FAIL, "Speech-to-text", f"server import failed: {error}")
        return
    try:
        server._get_stt_engine()
    except Exception as error:  # noqa: BLE001
        report.add(
            FAIL,
            "Speech-to-text",
            f"{error}\n          Spoken questions will 503. faster-whisper "
            "downloads its weights on first use, so this needs the internet ONCE.",
        )
        return
    import os

    report.add(
        PASS,
        "Speech-to-text",
        f"whisper '{os.getenv('CALM_WHISPER_MODEL', 'small')}' on "
        f"{os.getenv('CALM_WHISPER_DEVICE', 'auto')}",
    )


def check_timeout_budget(report: Report, provider) -> None:
    """The reviewed fallback has to arrive before Unity abandons the request."""

    info = provider.status
    timeout = float(info.get("timeout_seconds") or 0)
    attempts = getattr(provider, "max_attempts", 1)
    worst = timeout * attempts + 2 * (attempts - 1)
    unity_voice_timeout = 40
    if worst < unity_voice_timeout:
        report.add(
            PASS,
            "Timeout budget",
            f"worst case ~{worst:.0f}s < Unity's {unity_voice_timeout}s",
        )
    else:
        report.add(
            WARN,
            "Timeout budget",
            f"worst case ~{worst:.0f}s exceeds Unity's {unity_voice_timeout}s. On a "
            "slow network the child is told the SERVER is unreachable when it is the "
            "MODEL. Lower CALM_OPENROUTER_TIMEOUT_SECONDS / CALM_OPENROUTER_MAX_ATTEMPTS.",
        )


def lan_address() -> str | None:
    """This machine's outward-facing IPv4, without needing a route to exist."""

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def check_sideload_config(report: Report, unity_root: Path) -> None:
    """The address in the headset's config must be this machine, today."""

    config_path = unity_root / "Builds" / "calm-assistant.json"
    here = lan_address()
    if not config_path.exists():
        report.add(
            WARN,
            "Headset config",
            f"{config_path} not found. Run CALM/Build/Push KALMA Config To Headset, "
            "which regenerates it.",
        )
        return
    try:
        base = json.loads(config_path.read_text(encoding="utf-8")).get("baseUrl", "")
    except (OSError, json.JSONDecodeError) as error:
        report.add(FAIL, "Headset config", f"unreadable: {error}")
        return

    if here and here in base:
        report.add(PASS, "Headset config", f"{base} matches this machine ({here})")
        return
    report.add(
        FAIL,
        "Headset config",
        f"{base} does NOT match this machine ({here}).\n          Every request "
        "will fail and be reported as 'Cannot reach the CALM service', pointing you "
        "at a server that is running fine. Re-push the config.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--expect-lan",
        action="store_true",
        help="also check Builds/calm-assistant.json against this machine's LAN address",
    )
    parser.add_argument(
        "--unity-root",
        type=Path,
        default=Path(r"C:\CALM\CALM_VR"),
        help="the Unity project, for the sideload config check",
    )
    args = parser.parse_args()

    print("CALM preflight\n" + "=" * 60)
    report = Report()

    check_crosswalk(report)

    import server  # after the crosswalk check, which explains a failure here

    check_corpus(report, server.assistant)
    check_model(report, server.rag_chat.provider)
    check_timeout_budget(report, server.rag_chat.provider)
    check_speech(report)
    check_speech_model(report)
    if args.expect_lan:
        check_sideload_config(report, args.unity_root)

    print("=" * 60)
    if report.failed:
        print("NO-GO -- a child will hit one of the FAIL rows above.")
        return 1
    if report.warned:
        print(
            "GO, DEGRADED -- the session will run, but read the WARN rows so you know\n"
            "what the learners will actually get."
        )
        return 0
    print("GO -- model, voice, speech and grounding all verified live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
