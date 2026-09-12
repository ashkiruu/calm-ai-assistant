# Phase 2: context-aware assistant implementation

## Implemented boundary

```text
Unity story + trusted state -> mission-contract validation -> deterministic P0/P1
Learner question -----------> scope boundary / curated P2 retrieval
School profile + route snapshot --------------------------> route authorization
Sanitized response event ---------------------------------> monitoring dashboard
```

Speech cannot change the hazard, phase, shaking state, alarm, route state,
teacher order, assembly status, re-entry intent, or release authorization. Raw
PDF text is not searched at runtime.

The development server exposes:

- `POST /api/v1/respond`: question plus complete trusted context;
- `POST /api/process-voice`: audio plus the same serialized trusted context;
- `GET /api/v1/missions`: validated mission summaries;
- `GET /api/v1/missions/{mission_id}`: the executable Unity state contract plus
  the exact development verification oracle; and
- `GET /health`: corpus, school-profile, mission, and lazy speech-model status.

## Smallest end-to-end contribution

The frozen development contribution is the 17-state contract in
`config/missions/school_earthquake.v1.json`. Its one main path covers before,
during, after, route selection, assembly, reporting, aftershock, and no re-entry.
It also declares two calm correction loops and a fail-closed no-route hold.

Use the same learner question through these representative states:

| State | Trusted difference | Expected result |
|---|---|---|
| `EQ-S-B02` | Unsafe object visible | `EQ-BEF-003` |
| `EQ-S-D01` | Indoor shaking; approved cover reachable | `EQ-DUR-001` |
| `EQ-S-D02` | Learner moves toward exit while shaking | `EQ-DUR-003` |
| `EQ-S-A01` | Shaking stopped; no teacher instruction | `EQ-AFT-007` |
| `EQ-S-A02` | Teacher order; primary blocked, alternate open | `EQ-AFT-001` plus configured alternate |
| `EQ-S-H01-NO-ROUTE` | Every configured route blocked | `EQ-AFT-001` plus fail-closed hold |
| `EQ-S-A04` | At assembly; headcount active | `EQ-AFT-008` |
| `EQ-S-A05` | Fictional missing-person report pending | `EQ-AFT-005` |
| `EQ-S-A06` | Assembly-area aftershock | `EQ-AFT-006` |
| `EQ-S-A07` | Trusted re-entry attempt before clearance | `EQ-AFT-004` |

This is evidence of context awareness because the question and hazard can stay
the same while phase, location, learner action, authority state, route state,
and assembly state change the selected protocol and permitted movement.

The claim is falsified if those safety-relevant changes do not change the
decision, speech overrides trusted state, an undeclared transition or wrong zone
is accepted, a blocked/unknown route is selected, or an unapproved card is
served in production mode.

The browser matrix treats its 16 callable states as independent contract cases,
not as one chronological playthrough. It compares exact EN/FIL/Taglish response
text, blocked actions, route, zone, movement authorization, and mission metadata.
The full main path and branch returns are verified separately by automated tests.

## Development corpus versus production

Development mode admits only `EVIDENCE_LINKED` cards under the explicit internal
decision in `corpus/development_approval.json`. Every response reports
`runtime_approved: false`.

Production mode admits only `RUNTIME_APPROVED`. None of the current cards has
completed the external review chain, so production mode intentionally returns a
safe fallback instead of silently serving a development card.

## Verification versus UAT

Automated engineering tests validate routing, state contracts, APIs, safety
precedence, route failure, privacy, and language-pack behavior. They do not add
a learner pre-test or post-test.

UAT remains the study's user-acceptance validation. Before UAT, integrate the
frozen contract into Unity, keep local safety guards independent of the API,
connect the minimized dashboard event, and complete an internal technical and
child-safety rehearsal.

## Next implementation increments

1. Build the Unity EQ School scene against mission revision `1.0.0`.
2. Add authenticated state transport and server-side anti-replay if requests
   leave a controlled local prototype network.
3. Replace the synthetic profile with the partner school's reviewed alarms,
   routes, assembly area, and DRRM procedure.
4. Complete PHIVOLCS/DepEd or local-DRRMO, child-safety, Filipino/Taglish, school
   DRRM, and VR implementation reviews; then update card lifecycle states.
5. Connect only sanitized `dashboard_event` objects to the monitoring dashboard.
6. Run the hardware voice smoke test, Unity integration tests, and planned UAT.
7. Create separate executable mission contracts for the approved fire and
   typhoon stories.

See `docs/EQ_SCHOOL_UNITY_INTEGRATION.md` for the exact Unity handoff.
