# CLAUDE.md — CALM AI Assistant (Phase 2 backend)

Persistent context for Claude Code in `C:\CALM\calm-ai-assistant`. Read before acting.

## Status: ACTIVE — work hands-on here

This is no longer a planning document. The assistant is **built, running, and already
integrated into the VR project**: `Assets/Scripts/Assistant/` in `C:\CALM\CALM_VR` contains
the live client, and the installer has been run across the eight mission scenes. Treat this
repo the way you treat CALM_VR — edit Python directly, run the tests, fix what is broken.

The old version of this file described an "ECC workflow" with commands (`/ecc-recall`,
`/ecc-config`) that do not exist in this environment, and pointed at two files that do not
exist (`calm_core/retrieval.py`, `config/protocol_cards.yaml`). Both are corrected below.

**What has NOT changed: this is safety-critical and externally unapproved.** The internal gate
is `INTERNAL_DEVELOPMENT_VALIDATED`. BFP / PHIVOLCS / PAGASA / DepEd / local-DRRMO / partner-school
approval are all still outstanding, production retrieval units are deliberately 0, and the
school profile is synthetic demo data. Nothing here is for a real emergency.

## What this is

A local FastAPI service (`server.py`) on `http://127.0.0.1:8010` that answers a Grade 4
learner's questions during a VR emergency drill. The architecture's whole point is that the
LLM is kept away from anything safety-critical:

1. Unity sends **trusted state** (hazard, phase, place, action, route/zone IDs, authority).
2. `router.py` makes P0/P1 decisions **deterministically** and emits reviewed EN/FIL/Taglish
   text. It never calls an LLM.
3. P2 questions retrieve **curated protocol cards only** — never raw PDF chunks.
4. Alarms, routes, assembly areas and reunification authority stay in local config/state and
   never enter embeddings or prompts.
5. Dashboard events are minimized — no question text, no raw voice, no child PII.

## This repo is under version control

`github.com/ashkiruu/calm-ai-assistant` (private), at **`C:\CALM\calm-ai-assistant`** — a
sibling of `C:\CALM\CALM_VR`, which is the layout `docs/QUEST_LAN_SETUP.md` already assumes
when it says "the `calm-ai-assistant` folder".

> **Why the layout was changed, 2026-09-16.** The repo was originally cloned *inside*
> `C:\CALM\calm-ai-assistant-main`, an older zip extract of the same project — so the codebase
> existed twice, one path apart, with only the inner copy tracked and only the outer copy
> holding a `venv`. A full session's work landed in the extract before anyone noticed and had
> to be hand-ported. The extract has been deleted; `C:\CALM\calm-ai-assistant-main.zip` remains
> as the pristine original.
>
> The cost was not just the re-port. The same two-copy problem is what produced the
> `tut_13_ask` drift and a `docs/` page referencing a `scripts/start_lan_server.ps1` that
> appeared to be missing. **If a second copy of this project ever appears again, resolve it
> immediately rather than working around it** — and `git rev-parse --show-toplevel` is the
> one-second check that tells you which copy you are actually in.

## Environment — INSTALLED AND RUNNING (2026-09-15)

The stack is built and verified on this machine. `README.md`'s `.\venv\Scripts\python.exe`
commands all work again verbatim — the venv it describes now exists.

| Piece | State |
|---|---|
| `venv` | Python **3.12.7** (from `C:\Program Files\Python312`), created in the project. `venv/` is gitignored |
| Dependencies | `requirements-dev.txt` installed at its **exact pins** — fastapi 0.110.0, uvicorn 0.28.0, faster-whisper 1.1.0, pymupdf 1.23.26, python-multipart 0.0.9, edge-tts 7.2.8, httpx 0.28.1 |
| Ollama | **0.34.0** installed via winget, `qwen2.5:3b` pulled (1.93 GB), verified **fully GPU-resident** on the RTX 3060 (`size_vram == size`) |
| Speech out | edge-tts working — `/health` reports `available: true`; real MP3s in both voices |
| Speech in | faster-whisper working, **CPU** (see the cuBLAS note below) |
| Tests | **178 run, 0 failures** (2026-09-16, after the `tut_13_ask` drift was resolved on both sides) |

- **The `py` launcher is broken on this machine.** It defaults to a 3.13 registration whose
  exe does not exist. Use `python` (3.12.7 on PATH) or the venv directly; never `py`.
- **`faster-whisper` 1.1.0 has a missing dependency.** It imports `requests`
  (`faster_whisper/utils.py:8`) without declaring it. It used to arrive via `huggingface-hub`,
  which has since moved to httpx, so a clean install of the pinned version **fails at import**.
  `requests` is installed explicitly here; add it to `requirements.txt` if the pins are ever
  refreshed.

```powershell
# the launch line this project actually uses
$env:CALM_WHISPER_DEVICE="cpu"
.\venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8010
```

| Page | What it is |
|---|---|
| `/` | Mission Control — 16-state full-oracle verification matrix |
| `/simulation` | Learner-facing low-poly classroom preview |
| `/rag` | LLM/RAG test page over the 55 implemented Unity tasks |
| `/health` | Health check |

LLM answers need **Ollama** running locally (`CALM_OLLAMA_URL=http://127.0.0.1:11434`,
`CALM_OLLAMA_MODEL=qwen2.5:3b`). Read README's GPU section before blaming latency on the model
— Ollama falls back to CPU silently. Check with `curl -s http://127.0.0.1:11434/api/ps` and
confirm `size_vram` is close to `size`. Measured here: 2.16 GB of 2.16 GB in VRAM, answers
generated in **0.4–1.8 s warm**.

- **A cold Ollama costs you the first answer, silently.** The very first `/api/v1/chat` after
  Ollama starts came back `llm_used: false`, `answer_source: "deterministic_fallback"` — a
  correct, reviewed sentence, so nothing looked broken. The model simply had not finished
  loading and `rag_chat.py:938-961` degraded as designed. Warm it with one throwaway request
  before a demo, and **read `llm_used`, never the text, to tell whether the model ran.**

### Speech runs on the CPU here, deliberately

`CALM_WHISPER_DEVICE=cpu` is set on the launch line. With the default `auto`, `/api/v1/voice-chat`
returns **HTTP 503 `Library cublas64_12.dll is not found or cannot be loaded`** on this machine.

That is a real gap in the fallback ladder, not a configuration mistake. `_cuda_is_usable()`
(`server.py:580-595`) probes by *constructing* a tiny CUDA model, and its docstring states the
assumption plainly: "a missing library surfaces only when a model is constructed." For **cuDNN**
that holds. For **cuBLAS it does not** — construction succeeds and the DLL is only resolved at
*inference*, which is past every `try/except` in `_get_stt_engine()` (`:530-571`). So the probe
returns True, `small` loads happily on CUDA, and the failure lands on the learner's first spoken
question. Installing the CUDA/cuDNN runtime or hardening the probe would fix it; pinning to CPU
sidesteps it.

Measured on CPU: Whisper `small` downloads (~484 MB) on the first voice request, that request
takes ~10 s end to end, and warm voice turns land at **~0.45 s**. English and Filipino prompts
both transcribed verbatim, and the Filipino one was answered in Filipino.

## Where things actually are

| Path | Purpose | Strictness |
|---|---|---|
| `calm_core/router.py` (701 ln) | Deterministic P0/P1 decisions | **CRITICAL** — no LLM, ever |
| `calm_core/rag_chat.py` (1007 ln) | P2 generation + retrieval | **HIGH** |
| `calm_core/question_scope.py` | Off-task / cross-hazard gating before retrieval | **HIGH** |
| `calm_core/mission_contract.py` (668 ln) | Versioned mission-state contract | **HIGH** |
| `calm_core/unity_crosswalk.py` | Loads + validates the Unity task mapping | **HIGH** |
| `calm_core/repository.py` | Card / retrieval-unit access | |
| `calm_core/llm.py`, `speech.py`, `session_log.py`, `school_config.py`, `messages.py` | supporting | |
| `config/unity_scenario_crosswalk.v1.json` | **The cross-repo contract** — see below | **CRITICAL** |
| `corpus/protocol_cards.jsonl` | The 47 curated cards (generated) | **CRITICAL** — DepEd-approved only |
| `corpus/card_specs/` | Card **sources** — edit these, not the JSONL | **CRITICAL** |
| `config/missions/school_earthquake.v1.json` | The one implemented mission contract | **HIGH** |
| `examples/*.json` | API contract fixtures — tests must match | **HIGH** |
| `tests/` | 8 unittest modules | **HIGH** — new code → new tests |
| `unity/` | A **snapshot** of the Unity-side C#. Not the live copy — see below | |
| `archive/` | Old material; exclude from searches | |

There is **no `config/protocol_cards.yaml`** and **no `calm_core/retrieval.py`** — the previous
version of this file invented both.

## API surface (`server.py`)

```text
GET  /api/v1/unity/tasks            # what Unity gates push-to-talk on
POST /api/v1/chat                   # KALMA conversational (typed)
POST /api/v1/voice-chat             # + STT, loads Whisper on first use
POST /api/v1/speak                  # TTS — the ONLY step that leaves the machine
POST /api/v1/respond                # deterministic trusted-state mission endpoint
GET  /api/v1/missions[/{id}]
```

`/api/v1/speak` calls a Microsoft neural-voice service, so it needs network. Only text CALM
itself authored is sent — never learner audio, never learner questions. Failure returns 503
and never blocks the answer, so an offline headset still gets its instruction as text.

## The cross-repo contract, and its one current break

`config/unity_scenario_crosswalk.v1.json` maps every Unity `task_id` to hazard/setting/phase,
the exact simulation instruction, and protocol-card IDs. `/api/v1/unity/tasks` serves it, and
`CalmAssistant.CanAskTask(taskId)` gates the microphone on it. **A task missing from that file
makes push-to-talk silently no-op in the headset** — no error, no "listening" state, nothing.

**RESOLVED 2026-09-16.** Both sides now carry `tut_13_ask`: CALM_VR's Tutorial was rewritten
into its 6-part shape with PART 3 "Talk to KALMA", and the validator passes strictly —
`errors: []`, 56 tasks, exit 0 — with no flag set. `import server` succeeds on its own and
`unity_crosswalk.unity_drift` is empty. The full suite is **178 tests, 0 failures**; the
drift-detector test that was correctly failing now correctly passes.

> For roughly a day this repo declared a Tutorial task the Unity project had never contained,
> which made the backend unstartable and crashed `import server` at test-collection time.
> Kept here because the failure mode will recur: the check is a *cross-repo* invariant, and
> either side can move without the other noticing.

Adding a Tutorial task is **storyboard content** — `docs/storyboard/00_Tutorial.md` in CALM_VR
governs it. Per that project's rules, flag it and ask; do not invent the row.

### This drift stopped the server from booting at all

`UnityScenarioCrosswalk.__init__` validates against the **live Unity project** — the path comes
from `unity_source.project_root` in the crosswalk JSON, which hardcodes `C:/CALM/CALM_VR`. That
path exists here, so `server.py:51` raised `CrosswalkValidationError` at import and the whole
backend was unstartable. It also crashed `import server`, which is why `test_api` and
`test_rag_chat` never even collected.

**`CALM_UNITY_DRIFT=warn` (added 2026-09-15) is the dev escape hatch.** No longer needed for
`tut_13_ask` — the drift is gone — but kept for the next time the two repos diverge.
Deliberate design:

- Validation **always runs at full strength**. Only the `raise` is negotiable, so the drift is
  printed to stderr at every single startup instead of being forgotten.
- It downgrades **only** the two task-id drift errors listed in `DRIFT_ERROR_PREFIXES`. Any
  other fault — bad schema, missing corpus, blocked card lifecycle — still raises even with the
  flag set. Verified by pointing `cards_path` at a nonexistent file in warn mode: it still
  raised.
- **Set it per process, never system-wide.** It is read from the environment, so exporting it
  globally would relax the same guard inside the test suite.
- `validate_crosswalk()` itself was **not** given a skip switch, so `scripts/validate_unity_crosswalk.py`
  and the dedicated drift test stay strict no matter what the environment says.

The flag is a way to keep working while the two repos are reconciled. It is not a fix, and
`tut_13_ask` remains unreconciled.

Check the contract whenever either side changes a task id:

```powershell
python scripts\validate_unity_crosswalk.py --unity-library "C:\CALM\CALM_VR\Assets\Scripts\Missions\MissionLibrary.cs"
```

It prints a JSON report and **exits 1 on error** (verified), so it is safe in a chain.

### `unity/` is a stale snapshot — do not copy it over CALM_VR

Compared file-by-file against the live project, ignoring CRLF — which makes every file look
100 % changed if you forget it:

- **6 of 8 identical**: `AIAssistantHUD`, `CalmAssistant`, `CalmAssistantInstaller`,
  `CalmPushToTalk`, `CalmWav`, `MissionHUD`.
- **`MissionManager.cs` is OLDER here** — it still builds the wall-mounted `MissionBoard`.
  CALM_VR replaced that with the head-anchored `MissionObjectives` panel. Copying this file
  into CALM_VR would revert an owner-directed change.
- **`CalmClient.cs` is NEWER here** — it carries `general_qa`, `retrieval_mode` and
  `OK_GENERAL_QA`, which CALM_VR's client lacks. The backend **does** emit those
  (`rag_chat.py`), so the shipped VR client currently cannot see general-QA mode. Unity's
  `JsonUtility` ignores unknown fields, so this is a missing capability, not a crash.

Treat CALM_VR as the source of truth for Unity code, and port deliberately, one file at a time.

## Verify

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe scripts\validate_missions.py                 # PASS, exit 0
.\venv\Scripts\python.exe scripts\validate_corpus.py                   # PASS, exit 0
.\venv\Scripts\python.exe scripts\validate_unity_crosswalk.py --unity-library "C:\CALM\CALM_VR\Assets\Scripts\Missions\MissionLibrary.cs"
.\venv\Scripts\python.exe -m scripts.audit_learner_agency --output reports\learner_agency_audit_<date>.json
```

After editing `corpus/card_specs/`, rebuild the generated artifacts **before** validating:

```powershell
.\venv\Scripts\python.exe scripts\build_protocol_cards.py
.\venv\Scripts\python.exe scripts\build_retrieval_units.py
```

### Baseline (measured 2026-09-16, not assumed)

`unittest discover -s tests` → **Ran 178 tests, OK** — no flag required, no failures.

That includes the drift-detector test
(`test_unity_crosswalk.test_schema_corpus_references_and_live_unity_validate`), which calls
`validate_crosswalk()` strictly and passes now that both repos agree. On 2026-09-15 it was
the single expected failure; if it ever fails again, it is doing its job — read it as
"the two repos have diverged," not as a broken test.

For reference, the pre-fix numbers this replaced: **106 collected, 13 errors + 1 failure**,
with `test_api` and `test_rag_chat` unable to collect at all because `import server` crashed.

## Choosing a model — 2026-09-16

`qwen2.5:3b` was judged not good enough. Before swapping it, the benchmark that would
judge the replacement had to be fixed.

### The benchmark was scoring rules the prompt no longer states

`scripts/benchmark_models.py` hard-coded `MAX_WORDS = 30` and a `single_sentence` check.
The prompt at `rag_chat.py:608` says **"one to three short, calm sentences and no more than
45 words."** So every model was being marked down for obeying the prompt it was given, and
the *"Single sentence 23/29 (79 %)"* row in the old `docs/MODEL_BENCHMARK.md` was an
artifact, not a model weakness. Nothing failed loudly when the prompt was relaxed — the
benchmark just quietly went on measuring the old rule.

Both numbers now come from the prompt: `MAX_WORDS` is **imported** as
`rag_chat.MAX_ANSWER_WORDS` rather than restated, and the check is `within_sentence_cap`
(≤ 3). Restating a constant across a module boundary is what allowed the drift; importing
it makes the same drift impossible.

Two smaller bugs fixed in the same file:

- **The console score and the report disagreed for the same run** (82 % vs 93 %). The
  console used `len(CHECK_LABELS) * rows` as the denominator, assuming every check applies
  to every row — but the word and sentence caps apply only to *generated* answers, never to
  deterministic fallbacks. It now uses `sum(applicable.values())`, the same denominator
  `render()` uses.
- **`--report` outside the repo crashed the run at the last line**, after every model had
  been scored and the file written (`relative_to` raises). It now falls back to the
  absolute path. This would have hit the first Colab run, where the checkout is elsewhere.

### The corrected baseline, and what it actually says

`qwen2.5:3b`, 44 questions, default settings: **93 % overall, median 411 ms.**

| Check | Score |
|---|---|
| Scope routed correctly | 44/44 |
| No internal terms leaked | 44/44 |
| Evidence matches hazard | 44/44 |
| Within 45-word cap | 26/29 |
| At most 3 sentences | 26/29 |
| **Answered in asked locale** | **35/44 (79 %)** |

**The dominant failure is language, not format or grounding.** Nine of 44 answers came back
in the wrong language — Filipino and Taglish questions answered entirely in English, e.g.
*"Ano ang gagawin ko?"* → *"Get under the configured learner desk, drop, cover, and hold."*
The deterministic parts of the pipeline (scope gate, evidence selection, term filtering) are
perfect and are not the model's doing anyway.

Raising `CALM_LLM_MAX_TOKENS` 128 → 256 changed almost nothing (94 % vs 93 %, locale 81 % vs
79 %), so truncation is **not** the cause. That hypothesis is ruled out.

### Where to run bigger models

The 6 GB RTX 3060 caps out near 8B and even that spills to CPU (`sailor2:8b` is 5.2 GB
against a card that also drives a display). Anything genuinely larger needs to run
elsewhere.

**Cloud testing needs no code change.** `OllamaClient` falls back to `CALM_OLLAMA_URL`
(`llm.py:44-46`) and the benchmark never overrides it, so pointing the harness at a remote
Ollama is one environment variable. For a hosted token API instead, `LLMProvider`
(`llm.py:27-31`) is a two-member protocol — `.status` and `.chat()` — so an OpenAI-shaped
adapter is roughly 40 lines.

`notebooks/CALM_model_benchmark.ipynb` runs the sweep on a Colab T4 (16 GB).
`scripts/make_colab_bundle.py` packs the 1.6 MB upload it needs. Details that matter:

- **The benchmark runs inside Colab, not over a tunnel.** `calm_core` imports only the
  standard library — verified by running the extracted bundle on a bare system Python with
  no venv and no `pip install` — so there is nothing to install, and keeping it local to the
  GPU keeps the latency column meaningful. A tunnel would be measuring the tunnel. The
  notebook's last cell still offers a `cloudflared` tunnel, but only for *interactive* use
  from Unity.
- **`OLLAMA_MAX_LOADED_MODELS=1` is load-bearing.** Ollama keeps a model warm for five
  minutes, so a sweep stepping 9B → 14B → 20B would try to hold two at once on a 16 GB card
  and fall back to CPU partway through a run that still looks like it is working.
- **A Colab timeout is scored as a deterministic fallback**, which *flatters* the model
  rather than failing it, so the notebook raises `CALM_OLLAMA_TIMEOUT_SECONDS` to 180.
- **Benchmarking carries no privacy question.** The 44 questions are a fixed reviewed
  fixture, not learner data. Cloud *deployment* is a separate decision.

**Candidates are SEA-specific first, size second**, because the measured failure is language.
[Sailor2](https://ollama.com/library/sailor2) is Qwen2.5 continually pretrained on 500B SEA
tokens and explicitly covers Tagalog, Cebuano, Ilocano and Waray (`sailor2:8b` 5.2 GB,
`sailor2:20b` 12 GB). AI Singapore's [SEA-LION](https://sea-lion.ai/) covers 11 SEA languages
including Filipino, published on Ollama under the `aisingapore/` namespace —
`aisingapore/Llama-SEA-LION-v3.5-8B-R`, `aisingapore/Gemma-SEA-LION-v3-9B-IT`, up to
`Qwen-SEA-LION-v4.5-27B-IT` and `Llama-SEA-LION-v3-70B-IT`. `qwen2.5:14b` belongs in the
sweep as a pure size control: if it beats the SEA models, the problem was capacity rather
than language coverage, and that is worth knowing before citing either in the manuscript.

Keep `qwen2.5:3b` in every sweep as the control, or the comparison has no zero point.

## Rules that still bind

- **Never use an LLM for routing decisions.** Deterministic logic only.
- **Never search raw PDFs.** Curated protocol cards only.
- **Never log child PII** — no name, address, medical detail, guardian identity, question text
  or raw voice in dashboard events.
- **Never skip validation** before a schema change.
- **Always update tests** when touching a request/response contract.
- `router.py` and the protocol cards are **review-only** territory: propose changes to safety
  wording, don't quietly rewrite them.

## Working with the VR half

`C:\CALM\CALM_VR` has its own `CLAUDE.md` and is authoritative for anything Unity. Its
storyboards in `docs/storyboard/` are authoritative for mission **content** — task rows, line
ids, phases. If something here needs a new Unity task or a new narration line, that is a
storyboard change: flag it and ask.

Networking on device: the client defaults to `http://127.0.0.1:8010`, correct for the Windows
Editor. On a Quest, loopback is the headset itself. Either run `adb reverse tcp:8010 tcp:8010`
and enable `Allow Android Loopback For Adb Reverse` on `CalmClient`, or bind `--host 0.0.0.0`
and point `Base Url` at the teacher PC's LAN address. Apply the school's network policy; do
not expose the development service publicly.

## Useful commands

Real skills in this environment: `/code-review [level]`, `/security-review`, `/run`.
(`/ecc-recall`, `/ecc-config` and `/plan` from the previous version of this file are not
available here.)

Run `/security-review` for changes to `router.py`, the protocol cards, or API endpoints.
