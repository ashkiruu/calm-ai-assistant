# CALM/KALMA full-stack VR audit — 2026-08-29

## Outcome

The development integration is coherent and runnable from browser through the
local service into the Unity mission client. KALMA now answers learner questions
conversationally, retains one completed turn for short follow-ups, shows what the
learner said, speaks when synthesis is available, and degrades to grounded text
when the model or TTS is unavailable. Unity remains the sole mission and movement
authority.

This is a verified development baseline, not approval for real-emergency or
unsupervised child use.

## Architecture and authority boundaries

| Boundary | Responsibility | May change Unity state? |
|---|---|---|
| `POST /api/v1/respond` | Deterministic school-earthquake state instruction/oracle | No |
| `POST /api/v1/chat` | Task-grounded typed learner question with one-turn context | No |
| `POST /api/v1/voice-chat` | Local transcription, then the same grounded conversation path | No |
| `POST /api/v1/speak` | Philippine neural voice for CALM-authored answer text | No |
| Unity `MissionManager` | Mission order, task completion, corrections, timers and results | Yes |
| Unity colliders/mission logic | Route, cover, hazard and prohibited-area state | Yes |

Learner speech and previous dialogue are never trusted state. They cannot select
a route, mark a task complete, or override local hazard guards.

## Material fixes in this pass

### Conversational backend

- Kept task selection and retrieval tied to the Unity `task_id` while allowing
  the learner's question to choose a useful teaching shape such as a reason,
  ordered “how” steps, or the next action.
- Added one-turn conversation context so “How?”, “Why?”, and “What next?” are
  resolved against the previous question and answer without storing a history.
- Added the v4 learner-agency hierarchy: immediate self-action first, prohibited
  boundary second, and adult/responder handoff only for genuinely controlled
  decisions. Scenario-bound practice actions no longer inherit contradictory
  real-world adult-handoff steps.
- Added crosswalk `practice_steps` for controller-level “How?” guidance and fixed
  `now/ngayon` and `next/susunod` so they do not invent a disaster phase.
- Made local-model outage a controlled, task-grounded fallback rather than an
  HTTP failure that leaves the learner without guidance.
- Bounded voice metadata before speech recognition, serialized transcription
  model access, and made CUDA initialization fall back to CPU.
- Kept session evidence on an explicit allowlist and made the health response
  disclose fields that still exceed the reviewed privacy policy.

### Browser simulation

- Replaced the typed learner-question call to deterministic `/respond` with
  `/chat`; voice now uses `/voice-chat`.
- Added an exact mapping from all 16 callable preview states to implemented Unity
  task IDs, guarded by an API regression test against the mission contract.
- Added one-turn memory and reset it when the selected mission state changes.
- Kept route and movement authorization under the trusted mission contract.
- Rendered learner and KALMA lines separately and labeled conversational versus
  deterministic evidence correctly.

### Unity/KALMA

- Installed `CalmClient`, `CalmAssistant`, `CalmPushToTalk`, audio, and scene
  references in all eight implemented mission scenes.
- Added robust late binding for runtime-created HUD/camera references and a task
  queue for service startup races.
- Added briefing-time model warm-up and reuse of the still-current first answer.
- Added procedural KALMA states: idle, listening, thinking, speaking, and error.
- Placed KALMA at a lower-right peripheral viewport anchor so it stays visible
  without covering the briefing, hazard, or route view. It is not a ray target.
- Added separate `YOU` and `KALMA` subtitle rows, with transcript logging disabled
  by default.
- Added hold-to-talk lifecycle, silence/short-tap rejection, microphone permission
  handling, generated start/response/error earcons, spatial voice, and restoration
  of ducked scene audio.
- Added URL/task validation, stale-task response rejection, timeouts, and an
  Android loopback guard.
- Removed unused Unity AI/Codex packages that were producing unrelated editor
  JavaScript noise.

The mission's authored `GuidanceStub` remains deterministic on purpose for local
task/correction text. KALMA's task-grounded explanation and learner conversation
sit beside it; an LLM is not allowed to become the mission-state authority.

## Verification evidence

| Check | Result |
|---|---|
| Python unit/API/RAG/privacy/speech/crosswalk suite | 174/174 passed |
| Python compileall | Passed |
| Python dependency consistency (`pip check`) | Passed |
| Browser JavaScript syntax | Passed |
| Browser console after conversational test | No errors or warnings |
| Live browser “Why?” then “How?” | Distinct grounded answers; both dialogue rows visible |
| Corpus validator | Passed: 47 cards, 141 review units, 3 source-gap cards |
| Mission validator | Passed; production/school gates truthfully remain false |
| Unity crosswalk | Passed: 8 missions, 55 tasks |
| Live learner-agency audit | Passed: 55 tasks, 165 normal/alone/how answers, 0 findings |
| Unity 6.3 LTS script compile | Passed with no C# errors |
| Unity Typhoon School mission auto-walk | Passed 7/7, 0 infractions, 0 missed timers, 3 stars |

Crosswalk status is 23 `ready`, 18 `local_review`, 10 `scenario_bound`, and 4
`evidence_gap`. Those labels remain visible instead of being converted into a
false production-ready claim.

The learner-agency audit uses the same local Qwen response path as Unity. It
covers every implemented task in all eight missions; it is not limited to the
Earthquake Home picture example. Its report is
`reports/learner_agency_audit_2026-08-29.json` and its repeatable harness is
`scripts/audit_learner_agency.py`. Of the final 165 answers, 164 were returned
directly from the model and one incomplete procedure was replaced by the shared
crosswalk grounding guard.

## Meta Quest run configuration

Editor Play Mode can use `http://127.0.0.1:8010`. Android loopback points to the
headset, not the teacher PC:

1. USB development option: `adb reverse tcp:8010 tcp:8010`, then enable
   `AllowAndroidLoopbackForAdbReverse` on `CalmClient`.
2. Classroom LAN option: start the service with `--host 0.0.0.0 --port 8010`
   and use the teacher PC's approved reachable LAN address as `BaseUrl`.

Do not expose this development service publicly. A final device check still
requires the target Quest headset, its controllers and microphone, an active
OpenXR runtime, and the actual classroom network.

## Genuine external and content blockers

- The corpus has zero `RUNTIME_APPROVED` retrieval units by design.
- The school profile is `DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED`.
- Three outdoor-fire protocol cards are `NEEDS_CURRENT_SOURCE`.
- BFP, PHIVOLCS, PAGASA, DepEd, local DRRMO, school DRRM, Grade 4 child-safety,
  Filipino/Taglish language, and VR implementation approvals are outstanding.
- Filipino generation can lose meaning or grammar; reviewed Filipino rationales
  need domain-grade authoring and human evaluation.
- Session-log fields beyond the currently reviewed privacy policy need explicit
  governance review before classroom data collection.
- Speech synthesis requires a network connection; subtitles continue when it is
  unavailable.
- Quest headset/controller/microphone comfort and hardware smoke testing was not
  performed during this desktop automation pass.

These items cannot be fixed honestly by code alone and are the remaining gates
to classroom deployment.
