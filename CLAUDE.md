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

### Credentials

**`OPENROUTER_API_KEY` lives in the Windows user environment, nowhere else.** Set it with
`setx OPENROUTER_API_KEY "sk-or-v1-..."` (or `[Environment]::SetEnvironmentVariable(...,'User')`)
and open a new shell; `calm_core/openrouter.py` reads it at call time.

It arrived once as a `key.txt` sitting in this repo's root — untracked, never committed, and one
`git add .` away from being published in a repo that is private today and may not be forever. The
value was moved into the environment and the file deleted. `.gitignore` now carries `key.txt`,
`*.key` and `secrets.*` as the seatbelt. **Never paste a key into a chat, a commit, or a file
inside the repo** — a key in a transcript is a key you have to rotate.

`GET /api/v1/auth/key` reports the account's credit and tier without revealing the key, which is
the cheap way to check limits before a sweep.

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

**`docs/AI_ASSISTANT_WORK_LOG.md` is the narrative record** of the 2026-09-15 → 09-17 assistant
work across both repos: the order things happened in, what was measured, what turned out to be
wrong, and the open items carried forward. This file tells you the current state; that one tells
you how it got here and which earlier claims were corrected. Read it before re-deriving a
decision — several of them were made, reversed, and re-made on evidence.

## API surface (`server.py`)

```text
GET  /api/v1/unity/tasks            # what Unity gates push-to-talk on
POST /api/v1/chat                   # KALMA conversational (typed)
POST /api/v1/voice-chat             # + STT, loads Whisper on first use
POST /api/v1/speak                  # TTS — always leaves the machine (see local_only)
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

**Before a live session, run the preflight first.** It is the only thing that checks
the stack rather than the configuration:

```powershell
.\venv\Scripts\python.exe scripts\preflight.py --expect-lan     # exit 1 on NO-GO
```

It really calls the model and really synthesises speech, because every failure that
matters is something configured correctly and unreachable anyway. **`/health` cannot
substitute**: its `"status": "ok"` is a hardcoded literal, `speech_synthesis.available`
only reports whether `import edge_tts` worked, and `api_key_configured` means "a
non-empty string exists". `/health` returns 200 on an air-gapped laptop. It stays that
way on purpose — Unity probes it with a 10 s budget and it must be instant.

`WARN` rows are decisions, not failures: they name what the learner will actually get
(reviewed deterministic text if the model is unreachable, silent subtitles if TTS is).

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

### `CALM_LLM_MAX_TOKENS=128` silently zeroes out every reasoning model

The default budget was chosen for `qwen2.5:3b`, which emits an answer and nothing else. On
OpenRouter that number **excludes three models from the comparison entirely, and it looks like
the models are broken.**

`z-ai/glm-5.2:free` and `inclusionai/ling-3.0-flash-vl:free` came back with empty `content` and
`OpenRouter returned no answer`. The raw response says why: `finish_reason: "length"` with
`reasoning_tokens` of **126 and 143 against a 128-token cap**. They are reasoning models, the
budget covers reasoning *and* content, and they spent all of it thinking. Raised to 1024, both
answer correctly in Filipino. `dots-studio/dots-3-note-preview:free` and
`nvidia/nemotron-3.5-lightning:free` recovered the same way — the latter had been returning its
own chain of thought (*"Here's a thinking process: 1. **Analyze User Input:**"*) as the answer.

- **Check `finish_reason` before believing "the model returned nothing."** `length` plus a high
  `reasoning_tokens` is a budget problem; `stop` with empty content is a model problem.
- **Reading only `choices[0].message.content` is correct and worth keeping.** Reasoning arrives
  in a separate `reasoning` field, so a learner can never be shown the model's internal
  monologue — except from a model that writes its reasoning into `content` anyway, which
  `nvidia/nemotron-3-super-120b-a12b:free` does. That is a real disqualifier for a child-facing
  assistant, and the word and sentence caps catch it.
- **A sweep and its control must share the budget.** Raising it also removes a mechanical brake
  on the 45-word rule, so word-cap compliance becomes a test of instruction-following rather
  than of truncation — better methodology, but it moves the incumbent's numbers, so re-run the
  control at the same setting rather than comparing against an older run.

### Licensing — "open source" is three different things, and one of them bites

The project needs models that are **open source**. That splits three ways, and only the first
two are defensible in a manuscript that claims openness:

| Tier | Meaning | In the sweep |
|---|---|---|
| **OSI-approved open source** | Apache-2.0, MIT — use, modify, deploy, no conditions | `nex-agi/Nex-N2.5-Pro` (Apache-2.0), `inclusionAI/Ling-3.0-flash-VL` (MIT), `zai-org/GLM-5.2` (MIT) |
| **Open weights, custom licence** | Downloadable and self-hostable, but conditions attached | Nemotron-3-Ultra-550B and Nemotron-3.5-Lightning (OpenMDW-1.1), Nemotron-3-Super-120B (NVIDIA Nemotron Open Model License) |
| **API-only** | No weights anywhere; cannot be self-hosted at all | `dots-studio/dots-3-note-preview` — **disqualified** |

Check it, do not infer it. `https://openrouter.ai/api/v1/models` carries a `hugging_face_id`
field: absent means no public weights. Then `https://huggingface.co/api/models/<id>` gives
`cardData.license` plus `license_name`/`license_link` when the licence is custom.

> **The incumbent is the licensing problem.** `Qwen/Qwen2.5-3B-Instruct` is **`qwen-research`**,
> not Apache-2.0 — a research/non-commercial licence. Most other Qwen2.5 sizes (7B, 14B, 32B…)
> *are* Apache-2.0; the 3B specifically is not. For a prototype that is fine, but a system headed
> for DepEd classrooms should not ship on a research-only licence, and a thesis that calls its
> model "open source" without qualification would be overstating it. Worth raising with the
> adviser, and an argument for replacing `qwen2.5:3b` regardless of how it scores.

**Open source and locally deployable are different filters, and the second is harsher.** A 550B
model is open-weights and completely unrunnable on a teacher's laptop; the 6 GB development GPU
caps out near 8B. If the thesis keeps its "runs locally, privately" claim, the real candidate set
is open-licensed models at roughly 8B or below — which is a much smaller list than the sweep, and
is where `sailor2:8b` and the `aisingapore/` SEA-LION 8B models earn their place.

### Free models on OpenRouter: check, do not assume

The `:free` roster **rotates** — 20 → 15 → 14 and back to 20 within weeks. An article
recommending `meta-llama/llama-3.3-70b-instruct:free` was already stale: it is not in the live
list. Query `https://openrouter.ai/api/v1/models` and filter on `id.endswith(":free")`.

Of 12 plausible free candidates smoke-tested with one Filipino prompt each, **7 were usable**.
The failures were worth one request each to discover rather than 44:

| Failure | Models | Meaning |
|---|---|---|
| upstream `429` | both Gemma 4 | Saturated, not broken. Retry later. |
| `ResourceExhausted` | `nemotron-3-nano-omni` | Upstream capacity. |
| refused | `thinkingmachines/inkling` ×2 | Needs a **data-policy change** in the account's OpenRouter privacy settings — an account decision, not a code one. |

**Account state matters more than the model list.** `GET /api/v1/auth/key` reports `is_free_tier`
and credit. With credit purchased, free models allow **1000 requests/day** instead of 50 — and
50/day is less than one 44-question sweep, so an uncredited account can benchmark exactly one
model per day.

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

## RAG pipeline audit and fixes — 2026-09-17

A correctness and performance pass over the RAG path. Four real defects, all reproduced before
being fixed and re-measured after. Suite: **198 tests, 0 failures.**

### The output scrubber was corrupting correct answers

`RESIDUAL_REFERENCE_PATTERN` (`rag_chat.py`) had an **optional** citation verb (`{_CITES}?`), so it
deleted the bare nouns *card*, *source*, *protocol* and the Filipino *protokol* wherever they
appeared — in ordinary prose, with no citation anywhere near. Measured, not theorised:

| Model wrote | Learner saw |
|---|---|
| `Do not go near the flood source.` | `Do not go near the flood.` |
| `Listen only to trusted sources like PAGASA.` | `Listen only to trusted like PAGASA.` |
| `Keep your ID card in your bag.` | `Keep your ID in your bag.` |
| `Makinig sa mga mapagkakatiwalaang sources.` | `Makinig sa mga mapagkakatiwalaang.` |
| `Stay low. Source: the safety cards.` | `Stay low..` |

The second row is the dangerous one: it deletes the **object of a safety instruction** and leaves a
fluent sentence that means something else. The fourth is the project's own documented
"amputated Filipino clause" failure — this time produced by our scrubber, not by a model.

The citation verb is now **required**; a bare noun is ordinary language. A match is also consumed
to the end of its clause, because stopping at the noun is what turned *"ayon sa protokol ng
paaralan"* into a dangling *", paaralan."*. Three things still mark a noun as machinery: a
citation verb, an adjacent `EQ-DUR-001`-style identifier, or a label colon.

### Truncated answers were dressed up as finished sentences

`llm.py` discarded Ollama's `done_reason` and `openrouter.py` discarded `finish_reason`, so a
generation cut off at the token cap was indistinguishable from a complete one — and then
`_normalize_learner_text` appended a full stop, shipping *"Stay under the table until the
shaking."* to a child and to TTS as though it were finished. `LLMResult.truncated` now carries the
signal, the full stop is suppressed when set, and `generation.truncated` reports it.

**`GenerationInfo` in `server.py` had to be updated too** — Pydantic silently drops undeclared
keys, so the field would have died at the response boundary and never reached Unity. That is the
trap `ResponseContractTests` exists to catch.

### The pipeline answered Filipino children in English

The deterministic floor — what the pipeline scores with **no model at all** — was **34/44 (77%)**
on locale. It is now **43/44 (97%)**. The cause was English-only trusted text leaking into
non-English conversations:

- `active_simulation_instruction` and `practice_steps` are single English strings in
  `config/unity_scenario_crosswalk.v1.json`; all 47 protocol cards carry full `language_pack`
  entries for all three locales. The code preferred the English crosswalk string over the reviewed
  localised instruction sitting beside it.
- `prohibited_practice_handoff` had **no locale guard**, unlike the `missing_configured_steps`
  condition directly above it, so it could discard a correct Filipino answer and substitute
  English. Eligible on 14 of 56 tasks.
- `AUTHORITY_PATTERN` was English-only (`teacher|guardian|adult|…`), so the guardrail never fired
  on a Filipino answer at all — disabled in exactly the locales the model is worst at.
  `messages.py` already used `guro` and `nakatatanda`; only this pattern had not been told.

New `_trusted_replacement` picks the reviewed card instruction for the requested locale, falling
back to the localised `FALLBACKS` rather than to English.

> **What this does and does not change, stated carefully.** With the floor at 97 % and
> `qwen2.5:3b` at 81 %, **the model is measurably worse than no model at all on language** —
> roughly 8 of its 29 generated answers come back in the wrong one.
>
> It does **not** invalidate the earlier model benchmarks, and an earlier draft of this section
> wrongly said it did. `qwen2.5:3b` scores 35–36/44 on locale *both before and after* these fixes
> — checked across four runs. The English-fallback bug sits on the `LLMUnavailable` path, which a
> working model never takes; the floor measurement forces all 44 questions down that path, which
> is why the floor moved 20 points while the live-model number did not move at all. The scrubber
> and guardrail fixes affect only answers containing *card*/*source*/*protocol* or hitting the
> handoff guardrail on 14 of 56 tasks — real defects, but rare in the 44-question fixture.
>
> The earlier benchmarks were weak for a different reason: **the metric, not the bugs.** See the
> benchmark section above — three of the six checks are the deterministic pipeline and every model
> passes them 44/44, which is why a nonexistent model scored 94 % overall and why the real models
> all landed in a compressed 91–98 % band. Locale is the only column that discriminates.

### Prompt trimming

Measured on `eq_home_6_dch` / `en-PH`: **5238 → 4861 chars**, median latency **701 → 604 ms**
(−14 %), with locale up 79 → 81 % and the leak check still 44/44.

- `indent=2` on the user payload → compact separators. Pure whitespace, ~350 chars on a one-card
  prompt and ~870 on a five-card one.
- **`protocol_id` is no longer sent to the model.** The prompt forbids it from uttering an
  identifier and the scrubber polices the ones that leak — putting `EQ-DUR-001` in front of a small
  model and then guarding against it twice is self-inflicted. `retrieved_evidence_ids` in the
  *response* is built from `evidence_cards`, so the audit trail is untouched. Two tests that used
  the prompt payload as a proxy for "which cards were retrieved" now assert on that response field,
  which is what Unity and the session log actually read.

**Do not "optimise" the evidence payload by sending one locale or dropping provenance** —
`_evidence_summary` has always done both. Checked before proposing it.

### The prompt now mirrors the learner's language — 2026-09-17

The routing was never the problem. Unity sends `locale = "auto"` (`CalmLocale.Auto`), and
`detect_locale` resolves it from the question's Filipino function words, so a Tagalog question
already arrived as `fil-PH` or `taglish-PH`. What the prompt then said was only **"Answer in
simple Filipino"** — a target language, with nothing tying it to the learner's own question and
nothing forbidding a switch partway through.

That gap produced the benchmark's `correct_locale` failures, and they came in two shapes:

1. A Filipino question answered wholly in English.
2. **A mixed answer** — an English opening clause on a Filipino body: *"That is about a
   different emergency. In this simulation, first, maging mahinahon sa approved safe area."*

The second is the more common and the more damaging: the first sentence a nine-year-old reads is
the one in the language they did not use. The cause is that the cross-hazard redirect and the
"in this simulation" frame read to the model as fixed scaffolding rather than as part of the
answer it is meant to translate.

`_mirror_language_rule(locale)` states the three things the old rule did not: mirror the learner,
cover the whole reply **including the opening clause**, and never change language partway. It
leads **both** non-English branches — note the `practice_bound` branch previously carried no
statement about the answer's language at all, only about translating the configured instruction,
which left every surrounding sentence unaccounted for. `en-PH` emits nothing, so English requests
pay no extra tokens.

Measured live on `deepseek/deepseek-v4-flash`, against the seven questions the benchmark report
recorded as `correct_locale` failures: **7/7 now pass**, and the headline case
(`"Paano kung may bagyo?"`, previously fully English) returns *"Iyan ay tungkol sa ibang
emergency…"* — the redirect clause itself translated.

> **A Taglish answer containing English is not a bug.** Two of the seven still open with *"That
> is about a different emergency"*, and that is valid Taglish, which mixes by definition. The
> project's own check (`correct_locale` in `scripts/benchmark_models.py`) asks whether any
> Filipino marker is present, and both satisfy it. Do not "fix" this by forcing pure Filipino
> into a `taglish-PH` answer.

## Headset-readiness pass — 2026-09-17

Traced the whole path from a child's push-to-talk press to KALMA speaking: **31
preconditions, 19 of which failed silently from inside the headset.** Fixed the ones
that stop it working. The full list, with what each failure looked like, is in
`docs/AI_ASSISTANT_WORK_LOG.md` §11.

### Spoken Filipino was transcribed as English

`/api/v1/voice-chat` accepts `locale="auto"` and passed it to
`WHISPER_LANGUAGE.get(locale, "en")`. `"auto"` is not a key, so **every spoken
question in the product was decoded in forced-English mode** — and `_transcribe`'s own
docstring says that makes Whisper "invent a fluent English sentence that was never
spoken". Unity sends `auto` on every voice question, so this was the only path a child
used. Typed Filipino worked; spoken Filipino did not, which meant the language-mirroring
prompt rule shipped the same day was defeated in production.

`auto` now reaches Whisper as `language=None`, `resolve_spoken_locale` combines the
audio's detected language with `detect_locale`'s reading of the text (Whisper can tell
Tagalog from English but has no concept of Taglish), and `_transcribe` **raises** on an
unknown locale instead of defaulting. `transcribed_language` rides in the response and
the dashboard event, so a mishearing is visible rather than silent.

### One unreachable model could occupy the server for ~16 minutes

`openrouter.py`'s reasoning-fallback retry was guarded by `if not
self.reasoning_effort: raise` — and the default effort is the **string `"none"`**,
which is truthy. So every `LLMUnavailable`, including "unreachable", re-ran the whole
4-attempt ladder. At 120 s per attempt on a network that drops rather than refuses
packets: ~16 minutes for one question, long after Unity gave up at 40 s. The endpoints
are sync `def`, so each one holds an AnyIO worker thread and enough of them stop
`/health` answering at all.

The retry is now gated on an actual HTTP 400 (the status travels on the exception),
and `.env` sets `CALM_OPENROUTER_TIMEOUT_SECONDS=15` / `CALM_OPENROUTER_MAX_ATTEMPTS=2`.
**Measured against a black-holed address: 192 s → 32 s**, inside Unity's timeout, so
the child gets the reviewed fallback instead of an error.

> The existing test did not catch it because it used a **400**, which is not in
> `RETRY_STATUSES` and so exits each ladder on its first attempt — the doubling is
> invisible at two sends. The unreachable case is now tested explicitly.

### `.env` was loaded too late to configure anything early

`load_env_file()` sat **below** the module-level `getenv` reads, so
`CALM_CORPUS_MODE`, `CALM_SCHOOL_PROFILE`, `CALM_MAX_AUDIO_BYTES` and — worst —
`CALM_UNITY_DRIFT` were silently unsettable from `.env`. `CALM_UNITY_DRIFT` is the
documented escape hatch for a crosswalk mismatch that otherwise **stops the server
booting at all**, so it was broken exactly where a facilitator would reach for it.
Moved to the top of the module.

### Other fixes

- **Whisper is warmed at startup** in a daemon thread. Measured: ~5.4 s to load and
  ~5 s to transcribe a 4 s question, so lazily the *first* question of a session took
  twice as long as the rest — the one a facilitator judges the system on. Fires on ASGI
  startup, not import, so the suite never loads a speech model.
- **A corpus defect no longer reports as a bad task id.** `except KeyError -> 404`
  wrapped the whole pipeline; only `UnknownTaskError` is a 404 now.
- First tests for the API error paths, which had none.

### Still open, from the audit and not yet fixed

- **The scope gate refuses real questions.** *"Can I take my toy?"* during a live earthquake is
  answered with a canned brush-off, and the same question is refused on some tasks and answered on
  others depending on incidental token overlap. `CLAUDE.md` previously called the deterministic
  parts "perfect"; the golden set only contains trivially off-topic refusals, so the benchmark
  cannot see this.
- **`in_hazard_off_task` on a critical task** sets `deferred=True` and then calls the model anyway,
  with during-phase evidence, to answer an after-phase question — labelled `completion_code: "OK"`.
- **`rag_chat.py` hardcodes `ProtocolRepository()`**, ignoring `CALM_CORPUS_MODE`, so the RAG path
  and the router can disagree about which cards are eligible.
- **No golden-answer test exists** anywhere; every "safety" test on the generation path asserts a
  prompt substring rather than an outcome.
- Prefix stability is still only **51 %** within a task and **9 %** across locales, because the
  system block puts locale- and task-variable text near the top. Reordering it is the largest
  remaining latency lever and is a pure string reshuffle.

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
