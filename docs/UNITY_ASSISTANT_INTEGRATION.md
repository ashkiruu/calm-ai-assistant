# Unity assistant integration

How the VR client asks CALM a learner's question, and what it may do with the
answer.

Scope: the assistant endpoints. The trusted-state envelope for
`POST /api/v1/respond` is documented in `EQ_SCHOOL_UNITY_INTEGRATION.md`, and
HUD placement in `CALM_UI_UNITY_HANDOFF.md`.

## The rule that shapes everything else

**Trusted VR state flows one way: Unity to CALM.** A learner's question is a
question, never an instruction. Nothing CALM returns may change mission state,
unlock a route, or mark a step complete. Unity owns state; CALM answers about it.

This is why the assistant is a separate service, and why `IGuidanceProvider` is
the only seam it needs.

## Two endpoints, two different jobs

Do not merge these. They answer different questions and carry different
guarantees.

| | `/api/v1/respond` | `/api/v1/chat` |
|---|---|---|
| Asks | "Given this trusted state, what is the approved instruction?" | "The learner asked this. What is a grounded answer?" |
| Input | Full trusted context envelope | `task_id` + question + optional previous turn |
| Decides with | Deterministic rules only | Deterministic scope gate, then a local model |
| Uses a model | Never | Only when matching evidence exists |
| Use for | Mission cues, hazard state changes, P0/P1 safety | Learner curiosity: "why", "what if" |

The `/simulation` previsualisation uses the mission contract as the trusted
state/route oracle, then sends typed questions to `/api/v1/chat` and recorded
questions to `/api/v1/voice-chat`. Learner speech therefore exercises the same
scope gate and one-turn conversation memory as Unity without gaining authority
over movement or mission state.

## Client

The delivery copies are in `unity/`; the active Unity project uses them from
`Assets/Scripts/Assistant/`. `CalmClient` mirrors the server's response model
field for field and exposes the closed value sets as constants, so a `switch`
cannot drift from the server silently.

```csharp
StartCoroutine(calm.Ask(
    taskId: currentTaskId,
    question: "What if there is a fire?",
    onAnswer: answer => Hud.ShowSubtitle(answer.response_text, answer.IsDeferred),
    onError:  message => Hud.ShowSubtitle(message, urgent: true)));
```

`CalmClient` keeps exactly one completed exchange in memory for the current
task and supplies it with the next request. This makes short follow-ups such as
“How?”, “Why?”, and “What next?” intelligible without creating a stored chat
history. A task change stops that exchange from being sent. The server uses it
only as dialogue context; it is never evidence, trusted state, or a route/action
authority.

For on-task guidance, the service follows the documented
[learner-agency policy](LEARNER_AGENCY_POLICY.md): KALMA gives the action the
learner can perform before any adult handoff. Scenario-bound tasks use the
crosswalk's exact simulation instruction and optional controller
`practice_steps`; their real-world evidence remains a guardrail rather than a
replacement procedure.

## Branch on `completion_code`, never on the text

| Code | What happened | What the HUD should do |
|---|---|---|
| `OK` | Answered from this task's evidence | Show normally |
| `OK_CROSS_HAZARD` | Answered about a different hazard, in a calm phase | Show normally |
| `OK_IN_HAZARD_OFF_TASK` | Answered about another stage of this hazard | Show normally |
| `DEFERRED_DURING_CRITICAL_TASK` | A hazard is live; the other emergency was postponed | **Show urgently** — the text carries the current safety cue |
| `NO_RELEVANT_EVIDENCE` | In scope, nothing curated answers it | Show, and consider prompting for the teacher |
| `OUTSIDE_DISASTER_SCOPE` | Not a disaster question | Show the redirect, keep the mission cue on screen |

`answer_source` tells you whether a model was involved. Deterministic replies
return in microseconds with `model` empty; generated ones take roughly 600 ms.
Do not show a spinner for the deterministic branches — they land before a frame.

## Keeping task ids in step

`task_id` must be a Unity task id. The crosswalk holds all 55, and drift in
either direction is an error, not a warning:

```powershell
.\venv\Scripts\python.exe scripts\validate_unity_crosswalk.py --unity-library "C:\CALM\CALM_VR\Assets\Scripts\Missions\MissionLibrary.cs"
```

It reads `MissionLibrary.cs` at the path in the crosswalk's `unity_source`
block, matching `Id = "..."`, and fails if Unity has a task the crosswalk lacks
or the crosswalk has one Unity dropped. **Run it after any mission rename.** A
renamed task that reaches the headset unchecked produces a 404 mid-lesson.

## Voice

`POST /api/v1/voice-chat` takes recorded audio plus `task_id`. Transcription is
local and the temporary file is deleted; learner audio never leaves the machine.
The transcript comes back on the answer, so a mishearing is distinguishable from
a bad answer. `MissionHUD` renders it on a cyan `YOU` row above the white
`KALMA` response row. The row is temporary and the transcript is not written to
the Console or session log.

Set `Locale` before recording. Whisper is told which language to expect; without
that hint it mis-detects short Filipino utterances as English and then invents
fluent English that was never spoken.

## Speech out is always networked

`POST /api/v1/speak` calls a Microsoft neural voice service, so it needs a
network connection. Only text CALM itself authored is ever sent.

This section used to call synthesis "the one networked step" and "the only part
of the pipeline that leaves the machine." That is no longer true: generation can
be served by a hosted provider, in which case the learner's question is sent too.
Check `local_only` under `rag_chat` in `/health` for the deployment in front of
you instead of assuming.

It returns 503 when unreachable. **Treat that as normal, not as an error.** Show
the subtitle and continue; a classroom without wifi still gets its safety
instruction.

| Locale | Voice |
|---|---|
| `en-PH` | `en-PH-RosaNeural` (Philippine-accented English) |
| `fil-PH` | `fil-PH-BlessicaNeural` |
| `taglish-PH` | `fil-PH-BlessicaNeural` |

## Before a session

1. Start Ollama, then confirm it reached the GPU:
   `curl http://127.0.0.1:11434/api/ps` should report `size_vram` close to
   `size`. Zero means it fell back to the CPU and answers will be roughly three
   times slower — see the GPU notes in `README.md`.
2. Start CALM: `.\venv\Scripts\python.exe -m uvicorn server:app --port 8010`
3. Call `CalmClient.CheckHealth` before the first mission.

In Windows Editor Play Mode, the installed `Base Url` of
`http://127.0.0.1:8010` reaches the same computer. On Meta Quest it does not:

- With USB development, run `adb reverse tcp:8010 tcp:8010` and enable
  `AllowAndroidLoopbackForAdbReverse` on `CalmClient`.
- Over a classroom LAN, run Uvicorn with `--host 0.0.0.0 --port 8010` and set
  `Base Url` to the teacher PC's approved, reachable LAN address.

The Android client rejects loopback by default so a headset build does not
silently talk to itself. Do not expose this development service to the public
Internet.

## Expected latency

Warm and GPU-resident, measured on an RTX 3050 laptop with `qwen2.5:3b`:

| Path | Median |
|---|---|
| Deterministic branches | under 1 ms |
| Typed question | ~1.2 s |
| Spoken question | transcription time + ~1.2 s |
| Synthesis | ~1 s |

The first request after an idle period pays a model load of several seconds.
`CalmAssistant` now starts that warm-up while the briefing panel is visible and
reuses the result for the first task when it is still current.

If Ollama is unavailable or times out, `/api/v1/chat` returns a deterministic
task-grounded instruction/evidence fallback instead of turning the missing
model into a failed learner interaction. The response metadata declares that
fallback; the UI must not imply that a model generated it.

## Session evidence

Every answer emits a sanitized `dashboard_event` on the response, and the server
appends it to `CALM_SESSION_LOG` (default `logs/sessions.jsonl`). Unity does not
need to write anything: set `CalmClient.SessionId` and the record follows.

`CalmAssistant` generates one id per mission, so a session's events group without
anything about the id describing the learner.

The log carries the decision and its grounding — task, hazard, phase, scope,
completion code, evidence ids, latency, and a decision trace — and **never the
question, the answer text, or the transcript.** That is enforced by an allowlist
in `calm_core/session_log.py`, checked at startup against `privacy_rules` in
`corpus/system_rules.json`, rather than by remembering to omit them at each call
site.

`python scripts/session_report.py` turns the log into a Markdown summary.

## Known limitations

**Filipino answers are generated, and the model sometimes gets them wrong.**
`qwen2.5:3b` has been observed dropping a negation — the reviewed card says
*"Huwag galawin"* (do not touch) and the model produced *"Pangalawin"*, a
non-word, with the negation gone. It also produces occasional ungrammatical
Filipino.

An automated validator was attempted and did not work: a vocabulary-containment
check missed the dangerous case, because the invented word shares a stem with
the real one, while flagging good answers. No reliable programmatic guard was
found.

The decision was taken to keep the model on all three locales rather than serve
reviewed text for Filipino. This is a known, accepted risk and it should be
stated in any evaluation write-up. The long-term fix is corpus work rather than
model work: the cards carry a `rationale` field in English only, so a Filipino
*why* question has no reviewed text to be answered from.

**Answers are capped at 45 words.** The HUD now reserves separate learner and
KALMA rows and allows up to three short teaching sentences. This is long enough
for an ordered “how” explanation while remaining peripheral and readable in VR.

## Verified development baseline (2026-08-29)

- Unity 6.3 LTS compiled the active project with no C# errors.
- The Typhoon School mission auto-walk passed 7/7 tasks, reached the debrief,
  and produced 3 stars with no infractions or missed timers.
- The crosswalk reconciled all 8 implemented missions and 55 task IDs.
- 174 backend/API/RAG/privacy/speech/crosswalk tests passed.
- The browser simulation completed a conversational “Why?” then “How?” turn
  while keeping movement authorization under the mission contract.

This does not replace the remaining Quest headset, controller, microphone,
OpenXR runtime, and classroom-network smoke tests.

## Not yet cleared for learners

Integration testing is fine. Real children are not, and that is a project gate
rather than a technical one: the school profile is still
`DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED`, three cards are `NEEDS_CURRENT_SOURCE`,
and BFP, PHIVOLCS, PAGASA, DepEd, and local DRRMO approval are all outstanding.
