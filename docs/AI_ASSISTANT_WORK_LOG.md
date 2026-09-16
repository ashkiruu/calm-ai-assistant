# AI assistant (KALMA) — work log

A chronological record of the work done on the CALM AI assistant: what changed, why,
what was measured, what turned out to be wrong, and what is still open.

- **Period covered:** 2026-09-15 to 2026-09-17.
- **Scope:** both halves of the assistant — the Python backend in this repo, and the
  Unity-side integration in `C:\CALM\CALM_VR`. The mission/storyboard/prop work in the
  VR repo is *not* covered here; that lives in `CALM_VR/CLAUDE.md`.
- **Relationship to other documents.** `CLAUDE.md` in this repo is the working context
  a developer reads before touching the code, and it carries the current state. This
  file is the narrative record: the order things happened in, the reasoning, and the
  dead ends. Where a subject has its own document, this file points at it rather than
  restating it — see `docs/MODEL_BENCHMARK.md` (generated results),
  `docs/UNITY_ASSISTANT_INTEGRATION.md`, `docs/PHASE2_IMPLEMENTATION.md`.

---

## 0. Where the two halves live

| Half | Path | Repo |
|---|---|---|
| Backend (FastAPI, RAG, router, STT/TTS) | `C:\CALM\calm-ai-assistant` | `github.com/ashkiruu/calm-ai-assistant`, private |
| Unity client + Editor tooling | `C:\CALM\CALM_VR\Assets\Scripts\Assistant\`, `Assets\Editor\` | `github.com/TyeBen123/CALM_VR` |

The contract between them is `config/unity_scenario_crosswalk.v1.json`, which maps every
Unity `task_id` to its hazard, phase and protocol cards. Either repo can move without the
other noticing, so `scripts/validate_unity_crosswalk.py` is run after any task-id change.

---

## 1. Repo consolidation and version control

**The problem.** The backend started as an untracked zip extract at
`…\calm-ai-assistant-main`, and for a period two diverging copies existed side by side.
Work done in one was invisible to the other, and neither was under version control.

**What was done.** Consolidated to a single location, `C:\CALM\calm-ai-assistant`, a
sibling of the Unity project. The 0.6 GB stale extract was deleted. Both repos are now
tracked and pushed.

**Why the sibling layout matters.** It is what makes the Unity Editor launcher able to
find the backend with no configuration: `Assets/../../calm-ai-assistant`. A user who
clones elsewhere sets the path once via a menu item (see §8).

---

## 2. Environment

Installed and verified the full runtime: FastAPI/uvicorn, the RAG stack, `faster-whisper`
for speech-to-text, `edge-tts` for speech. Two things were not smooth and are recorded
because they will recur on a fresh machine:

- **`faster-whisper` 1.1.0 imports `requests` without declaring it** as a dependency.
  It has to be installed explicitly or the import fails at runtime, not at install time.
- **Whisper's CUDA path is broken on this machine and fails in a way that defeats every
  fallback.** `_cuda_is_usable()` probes at *construction* and succeeds; `cublas64_12.dll`
  is then missing at *inference*, which is past every fallback, so the request dies as a
  503. Pinned `CALM_WHISPER_DEVICE=cpu`. The Unity launcher sets this too.

---

## 3. A privacy claim was removed, at the owner's direction

Several documents stated that learner questions "never leave the machine." That was true
of the local-Ollama configuration and stopped being true the moment a hosted provider was
an option. Every such claim was removed rather than qualified.

The code now carries the fact instead of the prose: `LLMProvider.status` exposes a
`local_only` boolean — `True` for `OllamaClient`, `False` for `OpenRouterClient` — and
`tests/test_openrouter.py::test_status_declares_that_questions_leave_the_machine` asserts
it. A claim that can drift silently was replaced with one a test holds in place.

---

## 4. Hosted models: the OpenRouter provider

`qwen2.5:3b` running locally was not strong enough. The requirement was to try bigger,
smarter, **open-source** models, with cloud hosting acceptable as a means to that end.

**Built `calm_core/openrouter.py`**, a second implementation of the existing two-member
`LLMProvider` protocol (`.status`, `.chat()`). `server.py` selects between them on
`CALM_LLM_PROVIDER` (default `ollama`).

Deliberate choices:

- **Standard library only — no `requests`, no SDK.** The Colab benchmark bundle runs with
  zero pip installs, and adding a dependency here would have ended that.
- **Distinct errors per HTTP status.** 401 says the API key is bad, 402 says out of
  credit, 404 says the model id is unknown, 429 backs off and retries honouring
  `Retry-After`. This is not polish: a bad key reported as "the service is unavailable"
  costs an hour at 9pm, and a rate limit that aborts a twelve-model sweep costs the run.
- **4xx is never retried with the same payload.** The one apparent exception is real and
  tested: a 400 triggers exactly one further attempt with the `reasoning` parameter
  removed, because some models declare reasoning mandatory and reject `effort: "none"`.
  That is a different request, not a retry.
- **`truncated`** was added to `LLMResult` and plumbed through to the API response, so a
  cut-off answer is visible rather than being dressed up as a finished sentence (§7).

13 tests cover the provider, all mocked — the suite never touches the network.

---

## 5. Credentials

The API key was provided in a plain text file in the repo. It was moved to the
`OPENROUTER_API_KEY` **User environment variable**, `key.txt` was deleted, and
`.gitignore` gained `key.txt`, `*.key`, `secrets.*`. The key was never printed to the
console or written into any file, scene or `EditorPrefs` entry.

The Unity launcher deliberately does **not** set the key: the child process inherits it
from the user environment, so it cannot leak into the VR repo.

> **A test was coupled to this, and it broke.** `openrouter.py:77` resolves
> `api_key or os.getenv("OPENROUTER_API_KEY", "")`, so the "missing key" test passed only
> while no key was configured. Once the key was set, the test constructed a *working*
> client and failed. Fixed 2026-09-17 by clearing the variable explicitly with
> `patch.dict`. Worth remembering as a class: a test whose result depends on ambient
> machine state is not a test.

---

## 6. Choosing a model

### 6.1 "Open source" is three different things

The owner's constraint was open-source models only, later relaxed to "paid is fine, but
open-source only — not closed cloud models." That distinction needed making precise,
because OpenRouter's catalogue mixes three categories:

| Tier | Meaning | Examples seen |
|---|---|---|
| OSI-approved | MIT, Apache-2.0 — genuinely open | DeepSeek (MIT), Ling (MIT), Nex-N2.5 (Apache-2.0) |
| Open weights, custom licence | Published weights, restrictions attached | Gemma, Llama-3, OpenMDW-1.1, NVIDIA |
| API-only | No published weights at all | excluded |

Verification method, rather than trusting model names: a model on OpenRouter carries a
`hugging_face_id` only when its weights are published; the HuggingFace API then gives
`cardData.license` / `license_name`. Both were checked before any model was called.

**This found a real problem with the incumbent.** `qwen2.5:3b` is **qwen-research**
licensed — non-commercial. The 7B/14B/32B models of the same family are Apache-2.0. The
model the project had been running was the one variant in its family that a thesis
prototype should not ship.

Free models were likewise verified as existing and callable before being benchmarked, not
assumed from a list.

### 6.2 The benchmark was measuring the wrong things

Three defects, each of which made published numbers mean less than they appeared to:

1. **It scored rules the prompt no longer states.** `MAX_WORDS` was hardcoded to 30 while
   the prompt says 45, and a dead `single_sentence` rule was still being checked. Fixed by
   importing `MAX_ANSWER_WORDS` from the source of truth.
2. **Deterministic fallbacks were scored as the model's own work.** A deliberately
   **nonexistent** model id scored **94% overall** — because every reply fell back to
   reviewed deterministic text that passes scope, evidence and leaked-term checks by
   construction. A model that answered nothing outscored several that answered.
3. **Only 29 of 44 fixture questions ever reach the model.** The other 15 are answered by
   the scope gate. So a third of every published score measured the pipeline, not the model.

**Fixed by splitting the checks:**

```python
PIPELINE_CHECKS = ("scope_correct", "evidence_matches_hazard")
MODEL_CHECKS    = ("no_leaked_terms", "correct_locale",
                   "within_word_cap", "within_sentence_cap")
```

Model checks are scored only on answers the model actually generated; a zero-generation
run is now **rejected outright** rather than reported; the report carries an explicit
*Coverage* row; and locale is scored only on `fil-PH` / `taglish-PH` questions, where it
is a real requirement.

**What this invalidated, stated honestly.** An earlier draft of `CLAUDE.md` claimed these
fixes "change what every earlier benchmark meant." The owner asked directly whether the
earlier benchmarks were therefore false. Checked rather than defended: `qwen2.5:3b`'s
locale score was 35–36 of 44 both before and after the rubric change. The *comparisons*
between models held; what changed was the *denominator* and the ability to tell pipeline
work from model work. The doc was corrected.

> A second, smaller correction from the same period: the console and the written report
> disagreed (82% vs 93%) because they used different denominators, and `--report` to a
> path outside the repo crashed at the final line on `relative_to`. Both fixed.

### 6.3 Reasoning tokens were eating the answers

DeepSeek V4 Pro answered only **19 of 44** questions. The rest were not refusals — the
model spent its entire budget thinking and returned empty content, which the pipeline then
scored as a deterministic fallback.

Cause: `CALM_LLM_MAX_TOKENS=128` is shared by reasoning and answer tokens. Fixed by
disabling reasoning by default (`reasoning: {"effort": "none"}`, overridable via
`CALM_OPENROUTER_REASONING`). Note that OpenRouter's `exclude: true` is **not** the same
thing — it only hides the reasoning tokens while still billing and consuming the budget.

Effect on DeepSeek Flash: **25/44 → 29/44 coverage, and 14/14 on locale.**

### 6.4 The sweep kept losing its own results

Two long sweeps were killed and lost everything, because the report was written only at
the end. Fixed with an incremental `save()` after each model. The fix paid off immediately
on the next interrupted run, preserving 5 of 6 models.

### 6.5 Final comparison

Reasoning off, corrected metric, all at 29/44 coverage:

| Model | Locale | Score | Median | p90 | Licence |
|---|---|---|---|---|---|
| **deepseek/deepseek-v4-flash** | **14/14** | **98%** | 2177 ms | — | MIT |
| nex-agi/nex-n2.5-pro:free | 12/14 | 94% | 1334 ms | 5801 ms | Apache-2.0 |
| inclusionai/ling-3.0-flash-vl:free | 12/14 | 91% | 1385 ms | 1622 ms | MIT |
| google/gemma-4-31b-it | 11/14 | 92% | 956 ms | 1768 ms | Gemma (custom) |
| ollama:qwen2.5:3b (incumbent) | 7/14 | 86% | 645 ms | — | research-only |

**Recommendation: `deepseek/deepseek-v4-flash`.** Best free option:
`inclusionai/ling-3.0-flash-vl:free`.

Note the incumbent's honest locale figure is **7/14 (50%)**, where the old rubric reported
"36/44 (81%)". That gap is the whole reason the rubric work was worth doing.

> **`docs/MODEL_BENCHMARK.md` is generated output and currently holds the older
> reasoning-ON sweep** — which is why DeepSeek V4 Pro shows 19/44 there. It is superseded
> by the table above. Re-run `scripts/benchmark_models.py` to regenerate it.

### 6.6 Colab tooling

`notebooks/CALM_model_benchmark.ipynb` and `scripts/make_colab_bundle.py` produce a 1.6 MB
bundle that runs a sweep in Colab with **zero pip installs** — the reason the OpenRouter
client is standard-library only.

---

## 7. RAG pipeline audit and fixes

The pipeline had not been verified end to end since the provider was added. Four real
defects were found and fixed; all are in `calm_core/rag_chat.py`.

### 7.1 The output scrubber was deleting correct words

`RESIDUAL_REFERENCE_PATTERN` treated the citation verb as *optional*, so it matched and
deleted bare nouns — "card", "source", "protocol", "protokol" — wherever they appeared in
a legitimate answer. The verb is now **required**, and the reference forms are matched
whole rather than by fragment.

A companion bug: scrubbing a trailing clause left doubled terminal punctuation. Now
collapsed with `re.sub(r"([.!?])\s*[.!?]+", r"\1", cleaned)`.

### 7.2 Truncated answers were presented as finished sentences

A cut-off answer had a full stop appended, making a half-sentence look complete — the
worst possible failure mode for safety instructions. `truncated` is now tracked from the
provider through `_normalize_learner_text` to the response metadata, and the full stop is
suppressed when the answer was cut off.

### 7.3 The pipeline answered Filipino children in English

The sharpest bug of the pass, and it was structural rather than model-related.

`config/unity_scenario_crosswalk.v1.json` gives each task a single English
`active_simulation_instruction`, and `practice_steps` are plain English too. Both become
**learner-facing answers**: once on the `LLMUnavailable` fallback path, and once when the
grounding guardrail replaces a model answer it believes has drifted.

The guardrail case was worse. `missing_configured_steps` was explicitly gated on
`locale == "en-PH"`; the sibling condition `prohibited_practice_handoff` directly beneath
it **had no locale guard at all**. So on a `fil-PH` or `taglish-PH` request it could
discard a *correct Filipino answer* and substitute English — on any of the 14 tasks whose
`mapping_status` is `scenario_bound` or `evidence_gap`.

The fix was available because the reviewed content already existed: all 47 protocol cards
carry complete `language_pack` entries for all three locales. A new `_trusted_replacement`
now prefers the card's localised instruction, falling back to `FALLBACKS[locale]["no_card"]`.
Tests were added asserting that a Filipino question is never answered in English **on any
path, including both guardrails**.

**Measured effect: the deterministic floor on locale rose from 77% to 97%** — an
improvement owed entirely to selecting the right reviewed string, with no model involved.

### 7.4 Prompt trimming

`json.dumps(..., indent=2)` on the user payload was pure whitespace — roughly 600 characters
per card. Changed to `separators=(",", ":")`.

> **What was checked and deliberately *not* changed.** It was tempting to propose sending
> one locale instead of three and dropping provenance and review metadata from the
> evidence. `_evidence_summary` already does exactly that. Verified before proposing it.

### 7.5 The prompt now mirrors the learner's language (2026-09-17)

Requested directly: the assistant should answer in Tagalog when asked in Tagalog.

**The routing was already correct, and that was worth establishing before writing anything.**
Unity sends `locale = "auto"` (`CalmLocale.Auto` in `CalmClient.cs`), and `detect_locale`
resolves it from the question's Filipino function words — returning `taglish-PH` when real
English words sit alongside a Filipino frame, and `fil-PH` otherwise. A Tagalog question
therefore already arrived at the prompt tagged as Tagalog.

The gap was in the prompt itself. It said only **"Answer in simple Filipino"** — naming a
target language, with nothing tying it to the learner's own question and nothing forbidding a
switch partway through. That produced the two failure shapes in §6.5's `correct_locale` column:
a Filipino question answered wholly in English, and — more often — a *mixed* answer with an
English opening clause on a Filipino body. The second matters more: the first sentence a child
reads is the one in the language they did not use. It happens because the cross-hazard redirect
and the "in this simulation" frame read as fixed scaffolding rather than as text to translate.

`_mirror_language_rule(locale)` states what the old rule did not — mirror the learner, cover the
whole reply including the opening clause, never change language partway — and leads **both**
non-English branches. The `practice_bound` branch had carried no statement about the answer's
language at all, only about translating the configured instruction, leaving every surrounding
sentence unaccounted for. `en-PH` emits nothing, so English requests pay no extra tokens.

**Measured live** on `deepseek/deepseek-v4-flash` against the seven questions the benchmark
report records as `correct_locale` failures: **7/7 now pass**. The headline case,
`"Paano kung may bagyo?"` — previously answered fully in English — returns *"Iyan ay tungkol sa
ibang emergency. Maging mahinahon at makinig sa guro, tagapag-alaga, o beripikadong abiso."*,
with the redirect clause itself translated.

Five tests were added to `LanguageAnchorTests`, covering both locales, the redirect-opening
clause, the practice-bound branch, and the absence of the rule on `en-PH`.

> **A Taglish answer containing English is not a failure.** Two of the seven still open with
> "That is about a different emergency", which is valid Taglish — it mixes by definition. The
> project's own `correct_locale` check asks whether any Filipino marker is present, and both
> satisfy it. An initial stricter regex flagged them; the regex was wrong, not the answers.
> Do not force pure Filipino into a `taglish-PH` reply.

---

## 8. Unity-side integration

### 8.1 The server now starts itself

`CALM_VR/Assets/Editor/CalmServerLauncher.cs` (new) starts the backend on entering Play
mode if nothing is already listening on port 8010.

The failure it prevents is silent, not loud: with no server, `CalmClient.FetchKnownTaskIds`
never returns, `CanAskTask` is false for every task, and push-to-talk simply does nothing —
no error, no state change. The project had already lost a debugging session to exactly that.

Choices worth knowing: it probes the port first and never starts a second server; it does
not block the Editor (`LoadKnownTasksWithRetry` already backs off); it leaves the server
running on exit, because restarting per Play would pay the cold-load cost every time; and
the console window is visible on purpose. Menu items live under `CALM/Assistant/`.

> `UseShellExecute` **must** be `false`. .NET throws if `EnvironmentVariables` is populated
> while shell-execute is true — and the provider and model are passed that way. This was
> caught by re-reading before shipping, not by a compiler.

### 8.2 The `tut_13_ask` crosswalk entry

Tutorial PART 3 ("Talk to KALMA") was dead on arrival because the crosswalk had no entry
for `tut_13_ask`, so `CanAskTask` returned false. This was resolved on the backend side as
a `general_qa` entry spanning all three hazards, referencing three real pre-existing
protocol cards (`EQ-BEF-001`, `FIR-BEF-002`, `TYP-BEF-002`).

While the drift was open it was not a degradation but a **hard stop**: the crosswalk is
validated at import time, so a task id present on one side and missing on the other made
the server unstartable and crashed `import server` at test collection. A
`CALM_UNITY_DRIFT=warn` opt-out was added — validation always runs, only the raise is
negotiable, and only drift-prefix errors are downgraded.

### 8.3 The tutorial answered but never advanced (2026-09-17)

Reported symptom: KALMA answers the learner, and the tutorial does not move on.

Two gates were stacked. The first is deliberate and stays — the task never auto-advances,
per the owner's own requirement; a CONTINUE button appears and pressing it is what
completes the task. The second was a bug: the button only appeared when the transcript
contained the literal word **"hazard"** (`AssistantStarterKeywords = { "hazard" }`).

Three things marked it as a defect rather than a design:

- **It was inverted.** `OnLearnerQuestionFailed` and the 12-second timeout both call
  `AllowContinue()` unconditionally. KALMA *breaking* let the learner proceed; KALMA
  answering correctly in different words did not.
- **The hint described a control that did not exist**, and named it "Next" when the button
  reads "CONTINUE". It also leaked `B or Y (V on desktop)` into VR-facing text, which an
  earlier pass had already cleaned out of the other five Tutorial hints.
- **It was English-only.** "Ano ang panganib?" contains no "hazard", so a `fil-PH` learner
  could not complete the task at all — the same shape as §7.3.

Fixed in `TaskSpeakToAssistant.cs`: any real answer now reveals CONTINUE, and the starter
question remains a nudge rather than a lock. `ControlHint` rewritten.

---

## 9. Verification status

Measured 2026-09-17, not assumed:

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **203 passed, 0 failures** |
| Live locale check, 7 previously-failing Tagalog questions (§7.5) | **7/7** answer in the learner's language |
| `scripts/validate_unity_crosswalk.py` against live `MissionLibrary.cs` | **exit 0**, `errors: []`, 9 missions, 56 tasks, 34 protocol cards |
| Unity compile after the `tut_13_ask` fix | **0 `CS` errors** |
| Backend repo | clean, all work committed |

---

## 10. Still open

Carried forward honestly rather than closed off.

**From the RAG audit, documented but not fixed:**

1. **Scope-gate false refusals.** "Can I take my toy?" is refused during a live
   earthquake — a reasonable child question treated as out of scope.
2. **`in_hazard_off_task` on a critical task** calls the model with wrong-phase evidence
   labelled `OK`.
3. **`rag_chat.py` hardcodes `ProtocolRepository()`**, ignoring `CALM_CORPUS_MODE`.
4. **No golden-answer test.** Nothing asserts that a known question produces a known good
   answer; the suite checks properties, not content.
5. **Prefix stability is 51% / 9%.** Per-task caching was identified as a latency and cost
   lever and has not been implemented.

**From the benchmark:**

6. **The fixture is too small where it matters most.** 44 questions, but only **14
   non-English generated rows** — so "14/14 on locale" rests on fourteen data points.
   Widening the fixture is the single highest-value next step for any claim about locale.
7. **`DEFAULT_MODEL` in `openrouter.py` is still `qwen/qwen3-32b`**, which is not the
   benchmarked recommendation. Nothing is broken — the Unity launcher sets
   `deepseek/deepseek-v4-flash` explicitly — but the code default and the documented
   recommendation disagree, and whichever is wrong should be changed.

**From the Unity side:**

8. **Nothing here has been tested on a Meta Quest 3.** The assistant defaults to
   `127.0.0.1:8010`, which on a headset is the headset itself; LAN operation and
   `insecureHttpOption` are a decision to take *with* a real server, not before.
9. **The CONTINUE button's discoverability is unverified by a human.** The control dock is
   its own always-visible anchor in Tutorial mode (yaw 40°, pitch −20°) and is *not*
   hidden behind the collapsible task tab — but nobody has watched a learner find it.

---

## 11. Corrections made to earlier claims

Kept deliberately, in this project's existing style, because the corrections are as useful
as the conclusions:

| Claim | Correction |
|---|---|
| The rubric fixes "change what every earlier benchmark meant" | Overstated. Model-to-model comparisons held; the denominator and the pipeline/model split changed. Verified against `qwen2.5:3b`'s unchanged 35–36/44. |
| The MCP bridge was blamed on a stale PID on port 6463 | Wrong. The real cause was a transport mismatch — Unity on HTTP 8080, the client on stdio — proved by speaking MCP directly to `http://127.0.0.1:8080/mcp` and getting `instance_count: 1`. The owner was sent round an unnecessary restart loop first. |
| A nonexistent model scored 94% and looked competitive | Not a model result at all. Deterministic fallbacks were being credited to the model. |
