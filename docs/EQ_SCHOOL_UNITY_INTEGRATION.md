# EQ School Unity Integration Guide

Status: **development vertical slice; not for real emergencies**  
Guide version: `1.0.0`  
Last reconciled: `2026-07-31`

This is the implementation guide for the first complete CALM mission. The
machine-readable source of truth is
`config/missions/school_earthquake.v1.json`. Unity can retrieve the same
validated contract from:

```http
GET /api/v1/missions/school-earthquake-minimal
```

The contract uses synthetic `SIM_*` cues and demo route/zone identifiers. It is
ready for software integration and UAT preparation, but it is not approved by a
partner school, PHIVOLCS, DepEd/local DRRMO, or child-safety reviewers.

## Frozen development baseline

| Component | Version or value |
|---|---|
| API | FastAPI `0.3.0` |
| Context contract | `1.2` |
| Mission ID | `school-earthquake-minimal` |
| Mission revision | `1.0.0` |
| School profile | `CALM_DEMO_ELEMENTARY_SCHOOL` |
| Profile status | `DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED` |
| Classroom | `CLASSROOM_A` |
| Assembly area | `ASSEMBLY_A` |
| Primary route | `ROUTE_CLASSROOM_A_PRIMARY` |
| Alternate route | `ROUTE_CLASSROOM_A_ALTERNATE` |
| Shaking cue | `SIM_EQ_SHAKING_CUE` |
| Evacuation cue | `SIM_EQ_EVACUATE_CUE` |

Unity must check `GET /health` at startup. Keep the development banner visible
while `corpus.runtime_approved` or
`school_config.valid_for_real_emergency` is false.

## Ownership boundary

Unity owns the story, physics, scene geometry, colliders, learner pose, teacher
NPC, trusted state flags, alarms, route snapshots, state sequence, correction
loops, and mission completion. Its local safety barriers remain active if CALM,
the network, or TTS fails.

CALM validates the complete state envelope, selects a reviewed protocol,
returns exact bilingual/Taglish text for P0/P1, resolves only configured routes,
and emits a privacy-minimized dashboard event. CALM does not advance the story
and does not invent a location, route, alarm meaning, or teacher instruction.

Learner speech is only a question. It cannot alter any trusted state field.

## Canonical state graph

The one narrative path is:

```text
EQ-S-B01 -> EQ-S-B02 -> EQ-S-B03 -> EQ-S-D01 -> EQ-S-D04
-> EQ-S-A01 -> EQ-S-A02 -> EQ-S-A03 -> EQ-S-A04 -> EQ-S-A05
-> EQ-S-A06 -> EQ-S-A04R -> EQ-S-A07 -> EQ-S-END
```

The non-ending safety loops are:

```text
EQ-S-D01/EQ-S-D04 -- run to exit --> EQ-S-D02 -- safe retry --> EQ-S-D04
EQ-S-D01/EQ-S-D04 -- approach glass/shelf --> EQ-S-D03 -- safe retry --> EQ-S-D04
EQ-S-A02/EQ-S-A03 -- no open route --> EQ-S-H01-NO-ROUTE
EQ-S-H01-NO-ROUTE -- trusted route update --> EQ-S-A02 or EQ-S-A03
```

| State | Learning beat | CALM protocol | Unity gate |
|---|---|---|---|
| `EQ-S-B01` | Identify nearest approved cover | `EQ-BEF-001` | Correct configured desk selected |
| `EQ-S-B02` | Keep away and report unsafe object | `EQ-BEF-003` | Tell Teacher succeeds |
| `EQ-S-B03` | Learn configured route and assembly area | `EQ-BEF-001` | Route and assembly identified; no movement authorization |
| `EQ-S-D01` | Drop, Cover, and Hold On | `EQ-DUR-001` | Protected pose established |
| `EQ-S-D02` | Correct run-to-exit attempt | `EQ-DUR-003` | Return to approved cover |
| `EQ-S-D03` | Correct glass/shelf approach | `EQ-DUR-002` | Short safe return to cover |
| `EQ-S-D04` | Remain protected | `EQ-DUR-001` | Trusted shaking-stopped event |
| `EQ-S-A01` | Wait with class | `EQ-AFT-007` | Trusted teacher evacuation event |
| `EQ-S-A02` | Resolve teacher-led route | `EQ-AFT-001` | Returned configured route is authorized and present in scene |
| `EQ-S-A03` | Walk with class on selected route | `EQ-AFT-001` | Trusted assembly trigger |
| `EQ-S-H01-NO-ROUTE` | Hold when no route is open | `EQ-AFT-001` plus `NO_APPROVED_OPEN_ROUTE` | New trusted route snapshot only |
| `EQ-S-A04` | Stay for headcount | `EQ-AFT-008` | Fictional missing-avatar prompt |
| `EQ-S-A05` | Report fictional missing avatar | `EQ-AFT-005` | Report handed to teacher; never search |
| `EQ-S-A06` | Protect during assembly aftershock | `EQ-AFT-006` | Trusted aftershock-stopped event |
| `EQ-S-A04R` | Resume interrupted headcount | `EQ-AFT-008` | Trusted headcount-completed event |
| `EQ-S-A07` | Reject uncleared-building re-entry | `EQ-AFT-004` | Stay at assembly |
| `EQ-S-END` | Mission complete | No API call | Local non-identifying summary only |

`EQ-S-A04R` prevents the old `A04 -> A05 -> A06 -> A04` infinite loop. The
safe-hold state makes a route failure explicit instead of silently keeping A03
in two incompatible route contexts.

## Complete request envelope

Send a full context snapshot on every call, never a delta:

```http
POST /api/v1/respond
Content-Type: application/json
```

```json
{
  "question": "What should I do?",
  "locale": "taglish-PH",
  "context": {
    "session_id": "random-non-identifying-id",
    "scenario_id": "school-earthquake-minimal",
    "mission_revision": "1.0.0",
    "state_id": "EQ-S-D01",
    "state_seq": 4,
    "previous_state_seq": 3,
    "previous_state_id": "EQ-S-B03",
    "transition_event": "SHAKING_STARTED",
    "context_contract_version": "1.2",
    "school_profile_id": "CALM_DEMO_ELEMENTARY_SCHOOL",
    "timestamp": "2026-07-31T10:00:00+08:00"
  }
}
```

The abbreviated example above shows the mission envelope only. The actual call
must also include every core and earthquake field. Copy a complete payload from
`examples/eq_school_request_protect.json` or expand the current state from the
mission endpoint.

For registered missions, the API rejects:

- an unknown state or mission revision;
- a predecessor/event pair absent from the state graph;
- `state_seq` that is not `previous_state_seq + 1`;
- a phase, location, action, route snapshot, or safety flag that differs from
  the state contract;
- a terminal-state call;
- an alarm whose configured phase or hazard conflicts with the context; and
- an internally selected P0/P1 protocol that differs from the frozen state.

The current API validates the declared pair but does not persist a session
counter. Unity must maintain the strictly increasing sequence and reject any
response whose `session_id`, `scenario_id`, `mission_revision`, `state_id`, or
`state_seq` no longer matches its current snapshot. Authentication and replay
protection belong in the future trusted Unity adapter.

## Route authorization

Unity always sends the configured primary request plus an explicit route
snapshot. In A02/A03 the frozen demonstration snapshot is:

```json
{
  "safe_route_id": "ROUTE_CLASSROOM_A_PRIMARY",
  "safe_zone_id": "ASSEMBLY_A",
  "route_snapshot_id": "SIM_ROUTE_SNAPSHOT_EVAC_001",
  "route_states": {
    "ROUTE_CLASSROOM_A_PRIMARY": "BLOCKED",
    "ROUTE_CLASSROOM_A_ALTERNATE": "OPEN"
  }
}
```

The expected result selects only
`ROUTE_CLASSROOM_A_ALTERNATE`. Unity may unlock that route only when all of
these are true:

- `context_status == "valid"`;
- `completion_or_error_code == "OK"`;
- `movement_authorized == true`;
- the returned route ID exists in the current scene and snapshot;
- its origin is `CLASSROOM_A`; and
- its configured destination is the returned `ASSEMBLY_A`.

If no configured route is open, enter `EQ-S-H01-NO-ROUTE`, keep all exits
locked, stay with the teacher, and wait for a new trusted route snapshot.
Learner speech and elapsed time never open a route.

## Transient flag rules

- `learner_heading_to_exit` is true only in D02.
- `near_falling_or_glass_hazard` is true only in D03.
- `unsafe_object_visible` is true only while the B02 object still needs to be
  reported.
- `injury_or_missing_person_known` may remain true after A05 because the
  fictional concern still exists.
- `injury_or_missing_person_report_pending` becomes false after the learner
  hands the report to the teacher. This prevents repeated reporting while
  preserving the fact.
- `learner_attempting_reentry` is true only for the blocked A07 attempt. A
  damaged or uncleared structure by itself must not suppress normal evacuation
  or assembly instructions.
- A06 sets `aftershock_active`, `shaking_active`, and `hazard_active` true and
  clears all three before A04R.

## Unity consumption sketch

```csharp
async Task AskCalmAsync(ContextSnapshot sent, string question)
{
    CalmResult result = await CalmClient.Respond(question, locale, sent);

    if (Current.session_id != sent.session_id ||
        Current.scenario_id != sent.scenario_id ||
        Current.mission_revision != sent.mission_revision ||
        Current.state_id != sent.state_id ||
        Current.state_seq != sent.state_seq)
        return; // stale response

    Dashboard.Emit(result.dashboard_event);

    if (result.context_status != "valid")
    {
        Movement.HoldWithTeacher();
        Tts.PlayExact(result.tts_text, result.priority);
        return;
    }

    Tts.PlayExact(result.tts_text, result.priority);

    if (result.completion_or_error_code == "OK" &&
        result.movement_authorized &&
        Routes.ExistsInSnapshot(result.selected_route_id, sent.route_snapshot_id))
        Routes.EnableOnly(result.selected_route_id);
}
```

Local colliders and locomotion guards execute before the network response.
Never cause debris impact, injury, trapping, punishment, or a jump scare for an
unsafe attempt; use a short calm correction and retry.

## TTS and dashboard

Speak `tts_text` exactly for P0/P1. A new P0 state interrupts lower-priority
audio. Trigger on state entry or an unsafe action, not every frame.

Forward only `response.dashboard_event`. Do not add the question, transcript,
raw voice, free-form conversation, child name, roster, real missing-child
identity, guardian details, medical details, face/video, real-world location,
or persistent device identifier. Use a fictional NPC token inside Unity and do
not send that token unless the protocol needs a non-identifying scenario value.

Assembly and reunification are separate. This mission ends at assembly and does
not simulate guardian verification or child release.

## Verification and release gates

Engineering verification currently covers the full main path, both during-
shaking correction loops, the no-route hold and trusted retry, reported-concern
handoff, aftershock precedence, re-entry intent, wrong-zone rejection,
out-of-order sequence rejection, terminal rejection, privacy-minimized events,
all three language packs, unknown-mission rejection, explicit-null mission
metadata rejection, cross-setting protocol isolation, and active-shaking
fail-closed behavior when no approved critical card applies. The browser's
16-case matrix additionally checks exact reviewed wording, blocked actions,
route, zone, movement authorization, and mission identity metadata.

Before partner-school deployment, replace every synthetic school value with a
versioned and signed school DRRM profile, authenticate the Unity state adapter,
complete the required domain/child-safety/language/VR reviews, move the selected
cards to `RUNTIME_APPROVED`, run Unity integration tests, and then conduct the
study's planned UAT. Automated tests are engineering verification, not a learner
pre-test or post-test.
