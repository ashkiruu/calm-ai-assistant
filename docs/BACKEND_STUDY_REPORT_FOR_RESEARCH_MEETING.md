# CALM Backend Study Report for the Research Meeting

Prepared: 2026-09-11  
Purpose: Study guide and truthful implementation report for the CALM post-defense research meeting.

## How to use this report

Read Sections 1 to 4 first if you only have a few minutes. They give you the
research story, the architecture, and the meaning of RAG in CALM. Read Sections
9 to 12 before the meeting: they contain the evidence, limitations, and likely
adviser questions.

This is an implementation report, not a claim that CALM is ready for classroom
deployment or real emergencies. That distinction is important and defensible.

## 1. One-minute explanation of the backend

CALM is not a normal chatbot attached to a VR application. It is a local backend
service that receives trusted information from the VR mission, selects only the
disaster-preparedness evidence relevant to that mission, and gives a short,
age-appropriate explanation to the learner.

The central safety rule is that **Unity owns the simulation state**. The backend
does not decide whether a learner completed a task, whether an exit is open, or
whether a route is safe. Unity's mission logic and colliders decide those facts.
KALMA only explains the currently trusted task and answers related questions.

For mandatory, state-sensitive safety cues, CALM uses deterministic rules and
reviewed language packs. For educational questions such as "Why?" or "How do I
do that?", it uses a constrained Retrieval-Augmented Generation (RAG) process
with a local Qwen model. The model does not search the internet or the raw PDF
manuals; it receives a small, curated set of relevant protocol-card facts.

The result is a hybrid architecture:

```text
Unity trusted state / task ID
        |
        +--> Deterministic safety router for state-critical cues
        |
        +--> Task crosswalk + curated protocol cards + local Qwen model
                  for learner questions and short explanations
        |
        +--> Sanitized event record for future participation reporting
```

## 2. How this supports the proposal

The proposal defines three major outputs: the CALM VR application, the
context-aware AI assistant, and a monitoring dashboard. The backend work mainly
implements the second output and the safe data foundation for the third.

| Proposal objective | Backend contribution already implemented | Honest current status |
|---|---|---|
| Scenario-based activities that foster independent situational decision-making | Learner-agency policy; Unity-task grounding; controlled practice steps; safety boundaries that keep a learner from being told to wait for a teacher when they can safely perform the current practice action | Implemented and audited for the current 55 Unity tasks; not yet child-UAT validated |
| Continuous, context-aware AI support during missions | FastAPI service, task crosswalk, deterministic scope gate, local Qwen chat, voice input/output, one-turn follow-up memory, task-grounded fallback | Implemented for the current Unity integration; full state-contract coverage is still narrower than the full proposal scope |
| Centralized historical participation monitoring | Privacy-minimized `dashboard_event` object, append-only session log, and Markdown session-report script | Backend event foundation exists; a completed school-facing dashboard and approved school records workflow remain unfinished |

The proposal's central educational goal is independent situational decision-making.
The backend responds to that goal through the learner-agency hierarchy:

1. State the action the learner can safely do now.
2. State a relevant thing to avoid when needed.
3. Mention a teacher, guardian, or responder only when that part really needs
   adult authority, equipment, local knowledge, or training.

This does **not** mean a child can invent a route, re-enter a building, fight a
fire, rescue someone, handle utilities, or override an official instruction.
Independence means recognising and completing supported self-protection actions,
not taking adult or responder roles.

### Proposal-to-implementation scope check

The proposal describes three hazards across Home, School, and Outdoor settings:
9 possible mission combinations. The current backend crosswalk validates **8
implemented Unity missions and 55 tasks**:

| Hazard | Implemented settings | Current task count |
|---|---|---:|
| Earthquake | Home, School, Outdoor | 23 |
| Fire | Home, School | 12 |
| Typhoon | Home, School, Outdoor | 20 |
| Total | 8 missions | 55 |

This reveals one important gap for the meeting: **Fire Outdoors is described in
the proposal but is not yet one of the implemented crosswalk missions.** It must
be either completed, formally deferred, or reflected accurately in the scope and
limitations section of the manuscript.

## 3. What the backend is made of

### Technology stack

| Layer | Technology | Why it is used |
|---|---|---|
| API service | Python 3.11, FastAPI, Uvicorn | Provides typed HTTP endpoints that Unity and the web prototype can call locally |
| Language model | Ollama with `qwen2.5:3b` locally, or a hosted model via OpenRouter | Generates short, grounded educational explanations. Whether the learner question leaves the machine depends on which provider is configured — reported as `local_only` in `/health` |
| Knowledge layer | JSON/JSONL protocol cards and explicit Unity crosswalk | Keeps hazard, phase, setting, action, restrictions, provenance, and review status inspectable |
| Speech-to-text | `faster-whisper` | Transcribes learner speech locally; raw learner audio is not intentionally sent to an external transcription service |
| Text-to-speech | `edge-tts` Philippine neural voices | Gives KALMA natural voice output in Philippine English or Filipino; this is the one network-dependent backend step |
| Validation | Python `unittest` and project validators | Checks API contracts, routing, privacy, corpus, mission state, scope, speech, and Unity task mapping |
| Unity bridge | `CalmClient`, `CalmAssistant`, `CalmPushToTalk` | Sends task-grounded requests, displays responses, and preserves Unity as state authority |

### Main backend files

| File | Role |
|---|---|
| `server.py` | FastAPI boundary, input validation, endpoints, STT lifecycle, TTS calls, and session logging |
| `calm_core/router.py` | Deterministic context-aware safety routing for trusted state envelopes |
| `calm_core/mission_contract.py` | Validates the versioned school-earthquake state machine and legal transitions |
| `calm_core/rag_chat.py` | Builds grounded prompts, scopes questions, calls Qwen, normalizes output, and applies conversation guardrails |
| `calm_core/unity_crosswalk.py` | Maps Unity task IDs to the correct hazard, phase, task instruction, and curated evidence |
| `calm_core/repository.py` | Loads only protocol cards allowed by the development or production gate |
| `calm_core/question_scope.py` | Classifies whether a learner question is on-task, a different phase, a different hazard, or plainly off-topic |
| `calm_core/session_log.py` | Writes privacy-minimized telemetry records using an allowlist |
| `calm_core/speech.py` | Selects Philippine voices and synthesizes KALMA-authored text |
| `corpus/protocol_cards.jsonl` | Canonical curated knowledge records used by the backend |
| `config/unity_scenario_crosswalk.v1.json` | Validated Unity-task-to-evidence mapping |

## 4. The architectural principle: trusted state is separate from learner speech

This is the most important technical point to explain to an adviser.

If a learner says, "The exit is safe" or "I completed the task," CALM must not
believe that statement. The learner's words are treated only as a question.
Unity has the trusted facts because it knows the active mission task, player
position, current phase, detected hazards, route status, and progress.

```text
Learner voice/text                Unity mission system
        |                                  |
        | asks a question                  | owns trusted facts
        v                                  v
  /api/v1/chat or voice-chat        task_id or full state envelope
        |                                  |
        +--------------> CALM <------------+
                           |
                           v
                grounded answer / safe fallback
                           |
                           v
                  subtitle + optional speech

No CALM response is allowed to unlock a route, move a player, complete a task,
or change the mission state.
```

This design prevents a common safety problem in generative systems: treating
untrusted text as if it were evidence about the real or simulated world.

### Two backend pathways

| Path | Endpoint | Input | Purpose | Uses a model? |
|---|---|---|---|---|
| Deterministic mission instruction | `POST /api/v1/respond` | Full trusted VR context envelope | State-dependent cues, P0/P1 safety routing, route and authority logic | No |
| Conversational assistant | `POST /api/v1/chat` | Trusted Unity `task_id`, learner question, locale, optional one previous turn | Answers "what," "why," "how," and bounded related questions | Local Qwen only when evidence is available |
| Voice conversation | `POST /api/v1/voice-chat` | Recorded audio plus the same trusted task information | Local transcription followed by the conversational path | STT plus the same chat logic |
| Speech output | `POST /api/v1/speak` | KALMA-authored answer text and locale | Optional spoken MP3 response | No LLM; external neural TTS service |

The deterministic school-earthquake contract currently has a versioned
17-state design with 16 callable states and one terminal state. It demonstrates
how the same learner question can receive a different approved result when the
trusted context changes - for example, when shaking starts, a route becomes
blocked, an aftershock happens, or re-entry is attempted without clearance.

The conversational crosswalk is broader: it currently covers all 55 tasks in
the 8 implemented Unity scenes. This difference matters: **all implemented
tasks can receive task-grounded conversation, but a full deterministic state
contract has not yet been completed for every fire and typhoon story.**

## 5. The RAG pipeline: what it is and what it is not

### Simple definition

RAG means Retrieval-Augmented Generation. Before the model writes an answer,
the system retrieves the small set of trusted facts that may support that answer.
The model then generates within those facts instead of relying on its general
training memory.

In CALM, RAG is deliberately **constrained and structured**, not an open-ended
chatbot search.

### What CALM does not do

- It does not upload a child question to a generic cloud chatbot.
- It does not search the public internet at runtime.
- It does not directly search, embed, or feed entire disaster manuals/PDFs to
  the model at runtime.
- It does not fine-tune Qwen on the manuals.
- It does not let semantic similarity alone decide a safety-critical action.
- It does not use a model to decide whether a route is open, an evacuation is
  authorized, or a learner has completed a task.

### What CALM actually does

```text
Official/manual/web source
        |
        v
Source audit and page-level traceability
        |
        v
Curated protocol-card specification
  - hazard, phase, setting, learner role
  - ordered actions and prohibited actions
  - English / Filipino / Taglish language packs
  - sources, page locators, conflict notes, approval status
        |
        v
Generated canonical protocol cards
        |
        v
Unity scenario crosswalk
  Unity task ID -> exact simulation instruction + card IDs
        |
        v
Runtime request
  task ID -> retrieve only mapped cards -> build bounded prompt -> Qwen answer
```

### The runtime retrieval sequence

When a learner asks a question in Unity:

1. Unity sends a known `task_id`, for example `eq_home_6_dch` for an
   earthquake Drop-Cover-Hold task.
2. The crosswalk validates that task ID and retrieves its exact simulation
   instruction, hazard, phase, setting, trusted flags, mapping status, and
   associated protocol-card IDs.
3. The scope classifier checks the learner question before broad retrieval. It
   classifies it as:
   - `on_task`;
   - `in_hazard_off_task` - another stage of the same hazard;
   - `cross_hazard` - another disaster type; or
   - `out_of_scope` - plainly unrelated content.
4. For an on-task question, the mapped cards are used. For a calm
   cross-hazard or different-phase question, the repository may rank a small
   filtered set of curated cards using reviewed content-token overlap.
5. The prompt gives Qwen only the active simulation context and the selected
   evidence. It explicitly prohibits invented actions, internal identifiers,
   ungrounded claims, and a teacher/guardian handoff where the learner can
   safely do the current task independently.
6. The output is checked and normalized. If the local model is unavailable,
   CALM returns a deterministic task-grounded fallback instead of leaving the
   learner with an error screen.
7. A sanitized decision record can be logged without storing the learner's
   question, answer text, or transcript.

### Why this is still RAG even without a vector database

CALM retrieves evidence before generation, so it follows the RAG pattern.
However, it is not a conventional "embed every PDF in a vector database and
ask an LLM to search it" system. The current design uses explicit task mapping
and constrained card retrieval because this is safer and easier to audit for
Grade 4 disaster-preparedness learning.

This is a strong answer if asked, "Is it really RAG?":

> Yes. It is a structured, safety-constrained RAG system. Retrieval happens
> first, from curated protocol cards linked to the active Unity task; generation
> happens second, using only that bounded context. We intentionally did not use
> raw-document vector search for safety-critical learner instructions.

### P0, P1, and P2 safety levels

| Level | Meaning | CALM behavior |
|---|---|---|
| P0 Critical | Immediate protection or a high-risk boundary | Deterministic reviewed wording; the model must not reorder or contradict it |
| P1 Important | Important instruction that still requires tight constraints | Trusted context selects the card; rendering remains bounded |
| P2 Educational | Explanation, clarification, or learning support | Local model may generate a short answer from curated evidence |

This hybrid model is why CALM can be conversational without allowing
conversation to become the authority for emergency state.

## 6. What we did with the manuals, PDFs, and other sources

### Source inventory and audit

The backend began with a source audit rather than feeding all PDFs directly to
an LLM. The current corpus contains:

| Item | Count |
|---|---:|
| Total registered sources | 23 |
| PDF sources | 20 |
| Web sources | 3 |
| PDFs approved for selective learner derivation | 5 |
| Reference-only PDFs | 11 |
| Archived PDFs | 4 |
| Raw PDFs used directly at runtime | 0 |

Each PDF was hashed, page-counted, extracted into page-level JSON records, and
audited for authority, relevance, currency, learner role, safety, and
derivability. Raw page text remains evidence and traceability material, not
runtime learner guidance.

### How a manual became a usable CALM knowledge record

The team did not simply copy text from manuals. Each acceptable instruction was
split into smaller, inspectable decisions. A protocol card records:

- hazard, phase, setting, and learner role;
- conditions under which it applies;
- ordered learner actions;
- prohibited actions;
- deterministic trigger, failure, completion, and safe-default logic;
- English, Filipino, and Taglish language packs;
- source ID, page locator, authority, and unresolved conflicts; and
- lifecycle and reviewer requirements.

The current corpus validates to:

| Corpus result | Count/status |
|---|---:|
| Protocol cards | 47 |
| Required hazard-setting-phase context bundles | 27/27 covered or explicitly marked as a gap |
| Critical cards | 26 |
| Validation cases | 43 |
| Review-candidate retrieval units | 141 |
| Production runtime units | 0 intentionally |
| Source-gap cards | 3 |

### Source decisions that show safety judgment

Some source content was intentionally not turned into learner instructions:

- A Grade 4 learner is not instructed to use an extinguisher, fight a real
  fire, handle LPG, repair utilities, perform rescue, give medical treatment,
  enter floodwater, or enter a damaged building.
- Static phone numbers, social-media accounts, and current-alert claims are not
  treated as permanent runtime facts.
- Adult-only operational instructions are separated from learner actions.
- When sources disagree or are out of date, the instruction is quarantined in
  a conflict record instead of being made available to the model.

Examples of source conflicts still needing review include child extinguisher
use, wet-cloth guidance in smoke, outdoor-fire content, current school fire
drill cadence, coastal evacuation sequencing, and the precedence of typhoon
shelter advice versus a verified evacuation order.

### Development gate versus production gate

The corpus has the status `INTERNAL_DEVELOPMENT_VALIDATED`. This permits
prototype development, tests, VR integration, and UAT preparation.

It does not mean that the content has approval for classroom or real-emergency
use. The production gate accepts only `RUNTIME_APPROVED` cards, and there are
currently **zero** such cards. That is intentional: the repository should fail
safely rather than pretend that external review is complete.

### The reviews still needed for the manuals and cards

| Reviewer/authority | Main responsibility |
|---|---|
| BFP | Fire actions, terminology, trapped-person wording, extinguisher boundary, outdoor fire |
| PHIVOLCS | Earthquake sequence, aftershock, indoor/outdoor distinctions, damaged-building boundary |
| PAGASA | Typhoon/flood terminology, alert language, floodwater boundary, evacuation precedence |
| DepEd/local DRRMO/school | Actual routes, alarms, assembly areas, reunification, local procedure |
| Grade 4/child-safety reviewer | Age appropriateness, cognitive load, role boundaries |
| Filipino/Taglish reviewer | Meaning equivalence, negation, timing, natural Grade 4 language, TTS clarity |
| VR implementation reviewer | Trusted-state availability, observable completion, fail-closed behavior, privacy |

## 7. Why we used Qwen 2.5:3B

### Short answer for the meeting

We used **Qwen 2.5:3B through Ollama** because the project needs a local model
small enough to run alongside a VR application on the available development
hardware, yet capable enough to follow a tightly constrained safety prompt.
The model is used for educational phrasing and learner questions, not as the
authority for mission state or critical actions.

### Why a local model was the default, and what changed

The original argument for running the model locally still holds:

- It reduces dependence on a permanent external AI API connection and API-key
  costs.
- It makes the model replaceable: the backend uses an `LLMProvider` boundary,
  so another evaluated model can be substituted later.

**What changed (2026-09-16).** That boundary now also has a hosted
implementation, `OpenRouterClient`, added because the development machine's 6 GB
GPU cannot run the larger multilingual models the evaluation needs. When a
hosted provider is configured, **the learner's question is sent to a third-party
service.** Earlier drafts of this report stated that learner questions are
processed locally and never sent to a cloud LLM; that is only true of the Ollama
provider and the claim has been removed rather than qualified.

Two things are unchanged and are worth stating separately, because they are the
stronger privacy properties: **learner audio is still transcribed locally and
never leaves the machine**, and the session log still structurally excludes
questions, answers and transcripts by allowlist (`calm_core/session_log.py`).

Which side of the line a given deployment sits on is reported at runtime as
`local_only` under `rag_chat` in `/health`, so it can be checked rather than
assumed. Using a hosted provider for real learners is a decision for the
adviser and the ethics review, not a configuration detail.

This does not mean the entire system is offline. TTS currently uses a Microsoft
neural voice service and therefore requires network access. The text answer and
subtitle remain available when TTS fails.

### Why the 3B size matters

The development machine has a limited GPU memory budget, and Unity, Whisper,
and an LLM may need to coexist. The benchmark script notes that only one model
fits in the available 4 GB VRAM at a time, so switching models causes a reload.
A larger model could improve some language quality but would add startup delay,
memory pressure, heat, and instability on the target device setup.

For a VR companion, a short answer in roughly one second is more useful than a
larger answer after many seconds. KALMA has to feel responsive enough that a
learner can ask a question during a mission without losing the flow.

### How the choice was evaluated

The project includes a repeatable benchmark command:

```powershell
.\venv\Scripts\python.exe scripts\benchmark_models.py --models llama3.2 qwen2.5:3b phi3.5
```

The benchmark was designed to compare Qwen with `llama3.2` and `phi3.5` on 44
reviewed questions. It checks deterministic, auditable properties rather than
asking one model to judge another model:

- correct question scope;
- no leakage of internal terms such as card IDs;
- requested language/locale;
- retrieved evidence matches the answered hazard;
- answer-length compliance;
- sentence-format compliance; and
- warm GPU latency.

The persisted Qwen report dated 2026-08-28 records:

| Qwen 2.5:3B measure | Result |
|---|---:|
| Scope routed correctly | 44/44 (100%) |
| No internal terms leaked | 44/44 (100%) |
| Evidence matched the hazard | 44/44 (100%) |
| Asked-locale compliance | 40/44 (90%) |
| Overall deterministic benchmark compliance | 95% |
| Warm GPU median latency | 604 ms |
| Warm GPU p90 latency | 978 ms |

The local client code documents the decision that Qwen followed the prompt's
length and sentence rules more reliably than the tested Llama 3.2 and Phi 3.5
alternatives while responding at roughly half their latency on the development
hardware.

### Important honesty note about "why not the other models"

The code and benchmark command name `llama3.2`, `qwen2.5:3b`, and `phi3.5`,
but the currently saved Markdown benchmark table contains only Qwen's detailed
numbers. Therefore, do **not** invent exact comparative scores for Llama or
Phi in the meeting.

A safe statement is:

> We designed and used a deterministic benchmark for the three local candidates.
> Qwen 2.5:3B was retained because it gave the best practical balance of prompt
> compliance and latency within our hardware limits. The detailed saved report
> currently preserves Qwen's results; before final defense, we should rerun the
> same benchmark and retain the full three-model comparison table.

This is stronger than pretending a missing table exists. It also becomes a
clear, achievable improvement item.

### Known Qwen limitation: Filipino and Taglish

Qwen can produce grammatically incorrect or unsafe Filipino wording. A concrete
observed failure was loss of the negation in a phrase equivalent to "Do not touch
it." This is why the current report must say that Filipino/Taglish language
quality remains a known content and safety gap.

The long-term fix is not merely changing model temperature. It needs reviewed
Filipino and Taglish rationales, response templates, human language review, and
child comprehension testing. At present, English has the strongest verified
support.

## 8. Backend features we implemented

### A. Context-aware task grounding

The Unity crosswalk maps every current task to its exact simulation instruction
and supported evidence. It currently validates 8 missions and 55 task IDs.

This prevents a generic answer such as "go outside" from being used everywhere.
For example, a learner in an earthquake "drop, cover, and hold" task is not
given typhoon advice just because they ask an ambiguous question.

### B. Scope gating before generation

The system classifies a question before model retrieval. It knows the difference
between:

- a question about the active task;
- a question about a different phase of the same hazard;
- a question about another hazard; and
- plainly unrelated content.

During a critical live task, a cross-hazard question is deferred while the
current safety cue is retained. This prevents a learner from being distracted
away from the active protection action.

### C. Conversational follow-up support

Unity retains one completed question-answer exchange for the current task. This
allows short questions such as "How?", "Why?", or "What next?" to make sense.
The previous turn is never stored as permanent history and is never trusted as
mission evidence.

### D. Learner-agency policy

The assistant was corrected after testing showed that overly cautious responses
could tell a learner to find a guardian even during harmless simulation tasks.

The resulting project-wide policy was tested over every implemented task with
three question forms: normal next-action, explicitly-alone, and contextual
"How?". That is 55 tasks x 3 prompts = 165 live local-model answers. The final
audit found zero unresolved learner-agency issues.

For interaction-specific tasks, the crosswalk carries `practice_steps`, such as
grip, move, release, crouch, or hold duration. If the model omits a required
step or jumps ahead to a later mission task, a grounding guard returns the
complete trusted procedure. The model remains useful for natural explanation,
but it cannot replace the current Unity mechanic.

### E. Controlled fallback behavior

If Ollama is unavailable, times out, or produces unusable output, the learner
does not receive a generic server error as the only response. CALM falls back to
the exact active task instruction or a reviewed deterministic cue.

This is important in a classroom, where a model can be unloaded, GPU access can
fail, or a local process can be restarted.

### F. Voice interaction

Voice input uses `faster-whisper` locally. The speech model is loaded only when
the voice endpoint is used, so typing does not automatically consume GPU memory.
The backend:

- restricts audio file types and audio size;
- deletes temporary audio files after transcription;
- uses Filipino (`tl`) guidance for Filipino and Taglish transcription;
- uses a disaster-safety initial prompt to reduce irrelevant transcription; and
- serializes transcription to avoid concurrent GPU-buffer problems.

For TTS, CALM uses `en-PH-RosaNeural` for Philippine English and
`fil-PH-BlessicaNeural` for Filipino/Taglish. Speech is slowed by 10 percent for
Grade 4 listeners. If TTS is offline, subtitles remain the fallback.

### G. Privacy-minimized session evidence

The backend can log an event containing technical and mission metadata such as
task ID, scenario ID, hazard, phase, completion code, latency, and selected
protocol IDs. It intentionally does not log child names, raw voice, learner
questions, answer text, transcripts, addresses, medical details, or guardian
identity.

The protection is implemented with an allowlist: a field not explicitly allowed
cannot reach the JSONL log even if a caller accidentally passes it.

An important unfinished privacy item remains: some extended evaluation fields
are visible in the health status as beyond the initially reviewed privacy policy.
They require explicit governance review before any real classroom data
collection.

### H. Unity resilience measures

The Unity-side integration includes late binding for HUD/camera references,
startup task queues, stale-task response rejection, request timeouts, Android
loopback protection, model warm-up while the briefing is visible, and a safe
subtitle-first behavior when voice synthesis fails.

These are integration and user-experience improvements, not claims that the AI
controls the simulation.

## 9. Verification evidence available today

The following were freshly re-run on 2026-09-11 unless stated otherwise.

| Check | Current evidence |
|---|---|
| Python unit/API/RAG/privacy/speech/crosswalk suite | 174/174 passed |
| Corpus validator | Passed: 23 sources, 47 cards, 27/27 context bundles, 43 validation cases |
| Mission validator | Passed: 1 contract, 16 callable states, 1 terminal state; production/school gates remain false |
| Unity crosswalk validation | Passed: 8 missions, 55 tasks, 34 referenced cards; zero errors/warnings |
| Learner-agency audit | 165 live answers across all 55 tasks; 0 unresolved findings (2026-08-29) |
| Unity C# compile | Passed with no C# errors in the recorded full-stack audit |
| Typhoon School auto-walk | 7/7 tasks, 0 infractions, 0 missed timers, 3 stars in the recorded audit |
| Model benchmark | Qwen 2.5:3B report: 44 reviewed questions, 95% compliance, 604 ms median warm GPU latency |

### What these tests prove

They provide engineering evidence that the current code behaves as designed:
API contracts are valid, invalid state is rejected, task IDs do not drift from
Unity, privacy fields are filtered, model failure has a fallback, and the
current learner-agency policy holds for its tested prompts.

### What they do not prove

They do not prove that Grade 4 learners understand the wording, learn better,
feel comfortable in VR, use Filipino correctly, or perform well in real
emergencies. They are not substitutes for formal content review, ethics
approval, usability testing, or the quantitative evaluation planned in the
proposal.

## 10. Remaining work, prioritised honestly

### Priority 1: research and safety gates before learner deployment

1. **External content and safety review.** Obtain the required review of
   protocol cards from BFP, PHIVOLCS, PAGASA, DepEd/local DRRMO, school DRRM,
   Grade 4 child-safety, Filipino/Taglish language, and VR implementation
   reviewers. No current card is `RUNTIME_APPROVED`.

2. **Partner-school configuration.** Replace the synthetic demo school profile
   with approved local alarm meanings, primary/alternate routes, assembly areas,
   re-entry procedure, and reunification workflow. These facts must come from
   the partner school, not from a national PDF or the LLM.

3. **Filipino and Taglish remediation.** Do not claim these languages are
   production-ready. Add reviewed rationale text and direct-answer wording,
   conduct semantic-equivalence review, and test TTS comprehension with target
   learners.

4. **Ethics, consent, and child-safety process.** The proposal requires school
   and Division Office approval, parent/guardian consent, learner assent, and
   screening for phobias or sensory sensitivities before Grade 4 testing.

### Priority 2: close the proposal-to-implementation gaps

5. **Fire Outdoors module.** The proposal includes it; the current backend has
   only Fire Home and Fire School. Build the mission, obtain/curate the missing
   current source content, add its Unity crosswalk tasks, then extend tests and
   the learner-agency audit.

6. **Full deterministic state contracts for the remaining stories.** The
   versioned 17-state contract is a strong school-earthquake proof of concept.
   Fire and typhoon need equivalent fully validated state-machine contracts if
   the final study claims deterministic continuous state-aware support across
   every module.

7. **Monitoring dashboard completion.** The backend creates a sanitized event
   stream, but a real administrator dashboard, approved school data store,
   access control, retention policy, and reporting workflow still need to be
   completed.

8. **Formal RAG evaluation.** The proposal names RAGAS and RAGChecker, Context
   Groundedness, and Task Completion Rate. The project has technical tests and
   audits, but it still needs a locked evaluation set, human claim annotations,
   documented thresholds, and recorded formal metric results.

9. **Repeatable full model comparison.** Re-run Qwen, Llama 3.2, and Phi 3.5
   with the same fixture and hardware settings, then preserve the complete
   comparative report rather than only the Qwen table.

### Priority 3: device and operational hardening

10. **Quest hardware testing.** Test actual headset controls, microphone,
    OpenXR runtime, comfort/motion sickness, audio ducking, TTS latency, and
    classroom network behavior.

11. **Authenticated transport if leaving a controlled local network.** The
    current prototype is intended for local development. If a teacher PC or
    dashboard server is exposed over a classroom LAN, add authentication,
    replay protection, deployment configuration, and network policy review.

12. **Reliable offline policy.** Local LLM and STT can run locally, but TTS
    requires a network. Decide and document the classroom behavior when online
    voice synthesis is unavailable; subtitles already provide a safe fallback.

13. **Real UAT and quantitative analysis.** Conduct the planned Grade 4 pilot,
    administer the four-point ISO/IEC 25010-based questionnaire, compute
    weighted means, and clearly distinguish usability evidence from learning
    effectiveness.

## 11. Recommended wording for the research meeting

### Good claims to make

- "We implemented a local, task-grounded AI assistant for the current CALM VR
  prototype."
- "The assistant is context-aware because it receives trusted Unity task and
  state information, not just the learner's text."
- "We use a constrained RAG pipeline: audited sources become protocol cards,
  and only task-relevant cards are supplied to the local model."
- "Safety-critical mission state remains deterministic and Unity-controlled."
- "The current build passed 174 automated backend tests and a 55-task
  learner-agency audit."
- "The backend is development-validated, not externally approved for real
  emergencies or classroom deployment."

### Claims to avoid

- Do not say "the AI decides the safe route" or "the AI controls the mission."
- Do not say "we trained Qwen on the manuals." We did not fine-tune it; we
  retrieve constrained context and prompt a local model.
- Do not say "the dashboard is complete" if the actual administrator UI and
  school-approved data workflow are not complete.
- Do not say "Filipino and Taglish are finished." They are a known quality gap.
- Do not say "production ready" or "approved by agencies" because no current
  retrieval card has achieved `RUNTIME_APPROVED` status.
- Do not report exact Llama/Phi benchmark scores unless the full comparison has
  been rerun and saved.

## 12. Likely adviser questions and concise answers

### "What makes the assistant context-aware?"

> It does not answer from the learner's text alone. Unity gives a trusted task
> ID or full state envelope containing the hazard, phase, setting, current task,
> and applicable conditions. The backend selects evidence from that context, so
> the same question can receive a different answer when the trusted scenario
> changes.

### "Is this only a rule-based chatbot?"

> It is a hybrid system. Critical, state-dependent safety instructions are
> deterministic because they must not be hallucinated. Educational questions
> use local Qwen generation, but only after the backend retrieves a bounded set
> of curated protocol-card facts. The model provides natural language; it does
> not become the safety authority.

### "Why use RAG instead of just prompting a model?"

> A general model can invent facts or mix hazards. RAG gives it only the
> relevant reviewed evidence for the active task, and the crosswalk prevents
> irrelevant manuals or raw PDF text from entering the answer. It is more
> traceable, auditable, and controllable.

### "Are you using a vector database?"

> Not in the current runtime. We use a structured card-based RAG approach:
> explicit Unity task mapping retrieves the right protocol cards, while a small
> token-overlap rank is used only for limited related educational questions. We
> chose this over raw PDF embeddings because it is safer for a child-focused
> disaster-preparedness prototype.

### "Why Qwen 2.5:3B?"

> It runs locally within the available hardware budget and showed a useful
> balance of constraint following and latency. The recorded Qwen benchmark had
> 95% deterministic compliance over 44 reviewed questions, with a 604 ms warm
> GPU median. We will preserve a complete rerun of the Qwen/Llama/Phi comparison
> before final defense.

### "Did you train the model?"

> No. We did not fine-tune a model on the manuals. We created a curated knowledge
> base and use RAG to supply only relevant facts at answer time. This makes the
> evidence traceable and easier to revise after expert review.

### "How do you prevent hallucinations?"

> We do not claim zero hallucination risk. We reduce it by separating trusted
> Unity state from learner speech, using deterministic rules for critical cues,
> retrieving only curated cards, enforcing scope checks, bounding the prompt,
> stripping internal metadata, rejecting unsafe task drift, and returning
> deterministic fallbacks when the model fails.

### "How do you protect student privacy?"

> Audio is transcribed locally and temporary files are deleted. The session log
> uses an allowlist and excludes learner names, raw audio, questions, answers,
> transcripts, addresses, medical details, and guardian identity. We still need
> privacy governance approval for extended evaluation fields before classroom
> data collection.

### "What happens without internet?"

> The local model and local transcription can still work if the required models
> are installed. Text subtitles remain available. The current neural TTS is
> network-dependent, so spoken output may be unavailable; the system must still
> show the grounded subtitle.

### "How does this help independent decision-making without replacing adults?"

> KALMA leads with the action a learner can safely do now, such as getting low,
> moving away from glass, or using the configured route. It only hands off tasks
> that genuinely require adult authority or training, such as route approval,
> rescue, re-entry, utilities, and real fire suppression.

### "What is your biggest limitation today?"

> The biggest nontechnical limitations are external content approval, school
> localization, Filipino/Taglish language validation, and real Grade 4 user
> testing. Technically, Fire Outdoors, a full dashboard workflow, and complete
> deterministic contracts for all missions remain unfinished.

## 13. Questions you can ask your adviser

Use these to get decisions that unblock the project rather than vague feedback.

1. Should Fire Outdoors be completed before the next evaluation, or formally
   stated as a deferred module in the revised scope?
2. For the proposed RAGAS/RAGChecker evaluation, what target thresholds and
   human-review process should we commit to before data gathering?
3. Is a protocol-card review packet acceptable for BFP/PHIVOLCS/PAGASA/DepEd
   validation, and which authority should be contacted first?
4. Should Filipino/Taglish voice interaction be disabled for the initial pilot
   until reviewed language packs and child comprehension evidence are complete?
5. Is the session-log foundation sufficient for the current study phase, or does
   the full school dashboard need to be completed before user testing?
6. Should the quantitative evaluation focus on functional suitability and
   usability first, or should we add a pre-test/post-test measure of preparedness
   learning as a later study phase?
7. Given headset availability, should the Grade 4 pilot use the proposal's
   calculated sample target or the school principal's manageable 30-40 learner
   staged pilot recommendation?

## 14. A simple presentation flow

1. Start with the problem: ordinary drills cannot give every learner individual,
   realistic, situational guidance.
2. State the design response: a low-poly first-person VR simulation plus a
   context-aware companion.
3. Explain the architecture in one sentence: Unity owns trusted state; KALMA
   retrieves curated evidence and explains the active task.
4. Explain the manuals: 20 PDFs and 3 web sources were audited; raw PDFs are
   not directly searched at runtime; 47 protocol cards were built.
5. Explain RAG: task ID retrieves the right card context, then local Qwen writes
   a short learner-facing answer.
6. Explain why Qwen: local, responsive, constrained, benchmarked; not trained
   on the manuals; not the safety authority.
7. Show evidence: 174 tests, 55-task crosswalk, 165-answer learner-agency audit.
8. End with honest remaining work: approvals, local school data, Filipino,
   Fire Outdoors, dashboard/UAT/device testing.

## 15. Quick glossary

| Term | Meaning in CALM |
|---|---|
| API | The backend's set of endpoints that Unity calls over HTTP |
| FastAPI | The Python framework that exposes those endpoints |
| Ollama | Local runtime used to run Qwen on the development machine |
| Qwen 2.5:3B | The selected small local language model used for constrained educational responses |
| RAG | Retrieve relevant approved evidence first, then generate a response from it |
| Protocol card | A structured, traceable safety record derived from audited sources |
| Crosswalk | The mapping from a Unity task ID to its exact instruction and relevant protocol cards |
| Trusted state | Facts supplied by Unity/approved configuration, not by learner speech |
| Deterministic | Same approved input produces the same reviewed result without a language model |
| P0/P1/P2 | Critical, important, and educational levels used to decide how much generation is allowed |
| Grounding | Ensuring an answer is supported by supplied trusted context/evidence |
| Fail closed | When required safety information is missing, do not invent a permissive action |
| STT | Speech-to-text; Whisper turns voice into a transcript locally |
| TTS | Text-to-speech; KALMA answer text becomes spoken audio |
| UAT | User acceptance testing with intended users after appropriate approvals |

## 16. Evidence and file map

Use these files when you need to show the implementation during the meeting.

| Evidence | Location |
|---|---|
| API server and endpoint contracts | `server.py` |
| RAG prompt, scope, and grounding guard | `calm_core/rag_chat.py` |
| Deterministic state router | `calm_core/router.py` |
| Mission-state contract | `config/missions/school_earthquake.v1.json` and `calm_core/mission_contract.py` |
| Source audit summary | `corpus/SOURCE_AUDIT.md` |
| Corpus safety and review policy | `corpus/CORPUS_POLICY.md` and `corpus/EXTERNAL_REVIEW_GUIDE.md` |
| Canonical protocol cards | `corpus/protocol_cards.jsonl` |
| Unity task mapping | `config/unity_scenario_crosswalk.v1.json` |
| Model selection evidence | `docs/MODEL_BENCHMARK.md` and `scripts/benchmark_models.py` |
| Learner-agency policy and audit | `docs/LEARNER_AGENCY_POLICY.md` and `reports/learner_agency_audit_2026-08-29.json` |
| Full-stack verification summary | `docs/FULLSTACK_VR_AUDIT_2026-08-29.md` |
| Unity transport/voice integration guide | `docs/UNITY_ASSISTANT_INTEGRATION.md` |
| Current automated tests | `tests/` |

## Final takeaway

The backend contribution is not simply "we added an AI chatbot." We built a
controlled, local, task-aware assistance layer around the VR simulation:

- audited manuals became traceable protocol cards;
- Unity task IDs retrieve the right evidence for the learner's current situation;
- deterministic rules protect safety-critical state decisions;
- Qwen provides short, grounded educational explanations rather than unrestricted
  answers;
- voice, subtitles, and privacy-minimized evidence support the VR experience;
- automated validation proves the current software baseline; and
- external approval, language review, full scope completion, and real learner
  evaluation remain the necessary next research steps.

That is the most accurate and strongest way to present the work.
