# Unity Scenario to CALM Corpus Crosswalk

Status: development planning artifact; not a deployment approval  
Crosswalk version: 1.0  
Prepared: 2026-08-28

## Purpose

This document connects the eight implemented Unity hazard missions in
`C:\CALM\CALM_VR` to the curated CALM safety corpus. It is the design bridge for
future mission contracts, semantic retrieval filters, LLM prompts, and
context-aware evaluation cases.

The two inputs have different authority:

- Unity storyboards define what is happening in the simulation: scene, phase,
  task, object, scripted event, learner action, and handled deviation.
- Curated protocol cards define which safety claims, required actions,
  prohibited actions, and source references may ground a learner-facing answer.
- A storyboard sentence is not automatically general safety evidence. When a
  storyboard and protocol card use different boundaries, the task remains
  available as a simulation-specific instruction and is labelled so the LLM
  cannot generalize it outside the active VR state.

The storyboard files reviewed for this crosswalk are:

- `00_conventions.md` and `99_appendices.md`;
- `Earthquake_Home.md`, `Earthquake_School.md`, and
  `Earthquake_Outdoors.md`;
- `Fire_Home.md` and `Fire_School.md`; and
- `Typhoon_Home.md`, `Typhoon_School.md`, and `Typhoon_Outdoors.md`.

The implementation was reconciled against the task IDs in
`Assets/Scripts/Missions/MissionLibrary.cs`, not only the numbered prose rows.

## Adopted simulation-design decision

All currently implemented storyboard tasks remain usable in CALM VR. The
storyboard is the authority for what the learner is expected to do inside the
controlled simulation. A task is not removed merely because the general corpus
uses a more conservative real-world boundary.

The future LLM receives two separately labelled inputs:

1. `active_simulation_instruction`: the current task/action authored in the
   Unity storyboard; and
2. `retrieved_safety_evidence`: the relevant general safety claims from curated
   protocol cards.

When these differ, the generated answer must stay explicitly scoped to the
active simulation and must not generalize the simulated prop/action into
unsupervised real-world advice. For example, it may guide the learner through a
configured VR task while also explaining that real emergency routes and adult
instructions take precedence outside the simulation.

## Status legend

| Status | Meaning | RAG/contract treatment |
|---|---|---|
| `READY` | The simulated action has a compatible curated card. | May enter a development mission contract and RAG evaluation set. |
| `LOCAL_REVIEW` | Safety concept is supported, but the exact school/home route, cue, role, wording, or geometry needs stakeholder approval. | Keep development-only; retrieve the card but keep local values outside embeddings. |
| `EVIDENCE_GAP` | The exact simulated child action is not sufficiently described by a current general-safety card. | Keep the task as a scenario instruction, label it simulation-specific, and seek stronger evidence before generalizing it as real-world advice. |
| `SCENARIO_BOUND` | The current simulation intentionally asks the learner to perform an action for awareness or practice while the general corpus uses a more conservative boundary. | Keep and use the task only when its exact trusted Unity state is active. Do not turn it into context-free advice. |

## Current implementation inventory

| Unity scene | Implemented tasks | Proposed backend scenario ID | Current backend status |
|---|---:|---|---|
| `Earthquake_Home` | 9 | `unity-earthquake-home-v1` | Corpus cards exist; no mission contract. |
| `Earthquake_School` | 9 | `unity-earthquake-school-v1` | Existing `school-earthquake-minimal` contract does not match the implemented nine-task storyboard and should not be reused without reconciliation. |
| `Earthquake_Outdoors` | 5 | `unity-earthquake-outdoors-v1` | Corpus cards exist; no mission contract. |
| `Fire_Home` | 7 | `unity-fire-home-v1` | Corpus cards exist; two preparation tasks conflict with the child-safety boundary. |
| `Fire_School` | 5 | `unity-fire-school-v1` | Corpus cards exist; cloth and hot-item preparation tasks need correction/review. |
| `Typhoon_Home` | 9 | `unity-typhoon-home-v1` | Corpus cards exist; child cleanup and preparation roles need correction/review. |
| `Typhoon_School` | 7 | `unity-typhoon-school-v1` | Corpus cards exist; the floodwater-crossing task conflicts with the corpus. |
| `Typhoon_Outdoors` | 4 | `unity-typhoon-outdoors-v1` | Strongest typhoon alignment; local route/shelter approval still required. |

## Shared trusted context envelope

Every Unity request should send a complete snapshot. Storyboard text and learner
speech must never manufacture these values.

Common fields:

`session_id`, `scenario_id`, `mission_revision`, `state_id`, `state_seq`,
`previous_state_id`, `previous_state_seq`, `transition_event`,
`context_contract_version`, `hazard`, `phase`, `setting`, `location_type`,
`location_zone`, `learner_action`, `hazard_active`, `safe_route_id`,
`safe_zone_id`, `responsible_adult_present`, `timestamp`.

Hazard-specific trusted fields already defined in
`corpus/vr_context_contract.json`:

- Fire: `fire_or_smoke_confirmed`, `smoke_present`,
  `safe_exit_available`, `door_hot_or_smoke_leaking`,
  `no_safe_exit_available`, `learner_clothing_on_fire`,
  `reentry_not_cleared`.
- Earthquake: `shaking_active`, `aftershock_active`,
  `approved_cover_reachable`, `learner_heading_to_exit`,
  `near_falling_or_glass_hazard`,
  `structure_damaged_or_not_cleared`,
  `teacher_evacuate_instruction`, `at_assembly_area`,
  `headcount_active`, and related report/re-entry flags.
- Typhoon: `authenticated_evacuation_order`,
  `current_shelter_approved`, `trusted_safe_route_available`,
  `floodwater_present`, `rising_water_present`,
  `official_clearance_received`, and
  `downed_line_or_wet_electrical_hazard`.

Additional scene observations such as `learner_below_smoke`,
`learner_near_window`, or `learner_in_hazard_zone` may be added in a later
contract revision, but they must be computed by Unity colliders/mission logic,
not inferred by the LLM.

## Earthquake Home

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `eq_home_1_spot`, `eq_home_2_vase`, `eq_home_3_box`, `eq_home_4_picture` | `before`; visible elevated-object hazard; learner identifies and then moves three objects. | `EQ-BEF-003` (`REPORT_EARTHQUAKE_HAZARD`) | `SCENARIO_BOUND`. Retain the implemented lightweight-prop practice. The LLM may guide it only in this preparation state and must not generalize it into moving real heavy furniture, climbing, or repairing hazards. |
| `eq_home_5_cover` | `before`; learner identifies a configured sturdy table and route. | `EQ-BEF-001` | `READY`. The table/cover identity remains trusted scene configuration. |
| `eq_home_6_dch` | `during`; `shaking_active=true`; indoor; approved table reachable. Leaving the zone represents unsafe movement during shaking. | `EQ-DUR-001`; deviation also uses `EQ-DUR-003` | `READY`. Generate from retrieved required/prohibited actions; never from the line-id alone. |
| `eq_home_7_out` | `after`; shaking stopped; approved adult-led home route; broken-glass zone avoided. | `EQ-AFT-002` | `LOCAL_REVIEW`. The current simulation must make the responsible adult/clearance and approved route explicit; the learner must not self-authorize evacuation or touch damage. |
| `eq_home_8_aftershock` | `after`; `aftershock_active=true`; stop and re-protect in the approved location. | `EQ-AFT-006` | `READY`. |
| `eq_home_9_safe` | `after`; at the configured family meeting place; wait with adult. | `EQ-AFT-002`, with re-entry boundary from `EQ-AFT-004` when applicable | `READY` for development; family meeting location requires local configuration. |

## Earthquake School

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `eq_sch_1_map`, `eq_sch_2_route`, `eq_sch_3_cover` | `before`; learn the configured desk, route, and assembly location. No evacuation authorization. | `EQ-BEF-001` | `LOCAL_REVIEW`. Safety concept is ready; map, route, desk, alarm, and assembly identifiers require school approval and must remain configuration rather than embedding text. |
| `eq_sch_4_dch` | `during`; `shaking_active=true`; indoor classroom; desk reachable. Leaving cover/running is a deviation. | `EQ-DUR-001`; deviations `EQ-DUR-002` and `EQ-DUR-003` | `READY`. |
| `eq_sch_5_head` | `after`; learner retrieves/holds a book or bag above the head while evacuating. | Closest route card: `EQ-AFT-001`; unresolved corpus conflict `CF-003` concerns bringing a go-bag during school evacuation. | `EVIDENCE_GAP`. The exact book/bag behavior is not a required action in the current card and may conflict with “do not retrieve belongings.” Keep out of LLM grounding until PHIVOLCS/DepEd/local DRRMO and child-safety review approve the exact action. |
| `eq_sch_6_line`, `eq_sch_7_corridor` | `after`; teacher has authorized movement; walk on configured route; avoid glass; do not rush. | `EQ-AFT-001` | `LOCAL_REVIEW`. Route and pace are compatible. Add a reviewed post-earthquake route-hazard claim if “shattered glass” is to become an answerable fact rather than only a Unity collider rule. |
| `eq_sch_8_aftershock` | `after`; `aftershock_active=true`; stop movement and re-protect away from hazards. | `EQ-AFT-006` | `READY`. |
| `eq_sch_9_assembly` | `after`; `at_assembly_area=true`; class remains together for accounting. | `EQ-AFT-008` | `READY` for development; exact assembly location/headcount procedure requires school approval. |

## Earthquake Outdoors

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `eq_out_1_choice` | `before`; compare configured open area with tree, wall, pole, line, and facade hazards. | `EQ-BEF-002` | `READY`. |
| `eq_out_2_open`, `eq_out_3_low` | `during`; `shaking_active=true`; outdoor; short safe route to approved open area; protect head and remain. | `EQ-DUR-004` | `READY`. The open area is scene configuration, not an LLM invention. |
| `eq_out_4_aftershock` | `after`; aftershock starts while learner is already in the open. | `EQ-AFT-006`, `EQ-AFT-003` | `READY`. |
| `eq_out_5_evac` | `after`; remain clear of debris/fallen lines and follow an adult-approved path to the configured center. | `EQ-AFT-003` | `LOCAL_REVIEW`. Add explicit responsible-adult/authority clearance to the mission state; the learner must not independently choose a route or enter a building. |

## Fire Home

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `fire_home_1_spot` | `before`; learner notices an unattended candle and active stove. | `FIR-BEF-001` | `READY` only for identification, stepping away, and reporting to an adult. |
| `fire_home_2_candle`, `fire_home_3_stove` | `before`; child uses simulated preparation props to snuff a candle and turn off a stove. | `FIR-BEF-001`, safety boundary reinforced by `FIR-DUR-007`; corpus conflicts `CF-006`, `CF-008`, and `CF-009` | `SCENARIO_BOUND`. Retain the controlled pre-fire awareness tasks. The LLM must describe them as actions on the configured training props before an emergency, not as permission to approach a real active fire, hot appliance, or fire-suppression situation. |
| `fire_home_4_low` | `during`; `smoke_present=true`; learner lowers below the smoke layer. | `FIR-DUR-004` | `READY`. Hardware testing must calibrate the height threshold. |
| `fire_home_5_exit` | `during`; confirmed fire/smoke; approved exit available; learner crawls along the trusted route. | `FIR-DUR-001`, `FIR-DUR-004`; route guards may also invoke `FIR-DUR-003` or `FIR-DUR-006` | `READY` if Unity supplies route availability and never directs the learner through fire/smoke. |
| `fire_home_6_meet` | `after`; learner reaches the configured family meeting point. | `FIR-AFT-002` | `LOCAL_REVIEW`. Meeting point and responsible adult require household/scenario configuration. |
| `fire_home_7_stay` | `after`; remain outside; re-approaching the door is a deviation. | `FIR-AFT-001`, `FIR-AFT-002` | `READY`. |

## Fire School

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `fire_sch_1_exit` | `before`; move a lightweight box from the fire exit before an emergency. | `FIR-BEF-002` | `LOCAL_REVIEW`. Compatible with “keep exits clear,” but the exact learner role/object weight should be reviewed by the school and child-safety reviewers. |
| `fire_sch_2_paper` | `before`; child moves paper away from a hot plate. | `FIR-BEF-001` | `EVIDENCE_GAP`. The corpus tells the child not to touch hot items and to tell an adult. Prefer a report-to-teacher task, with the adult/NPC moving the paper or disabling the heat source. |
| `fire_sch_3_cloth` | `during`; learner holds the configured cloth prop over nose and mouth before lining up. | `FIR-DUR-004`; unresolved wet-cloth conflict `CF-007` | `SCENARIO_BOUND`. Retain the existing task because the prop is immediately available in the controlled scene. The LLM must not tell learners to delay evacuation to search for or wet a cloth in a real fire. |
| `fire_sch_4_line` | `during`; alarm/fire confirmed; teacher-led orderly evacuation starts. | `FIR-DUR-001` | `READY`; local alarm and teacher cue require school configuration. |
| `fire_sch_5_assembly` | `after`; use approved path, avoid smoke pocket, walk to assembly, remain for headcount. | `FIR-AFT-001`, `FIR-AFT-002` | `LOCAL_REVIEW`. Route, smoke-pocket state, assembly point, and headcount are trusted Unity/school state. |

## Typhoon Home

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `typ_home_1_pack` | `before`; child-safe go-bag practice with water, food, flashlight, first aid kit, whistle, and distractors. | `TYP-BEF-002`; medication/access conflict boundary `CF-010` | `READY` if the first-aid kit remains sealed/adult-controlled and the scenario excludes medicine, cash, documents, fuel, chemicals, knives, matches, and lighters. |
| `typ_home_2_loose` | `before`; child brings a loose toy indoors before conditions worsen. | Closest boundary: `TYP-BEF-002`, `TYP-BEF-004` | `EVIDENCE_GAP`. Add authoritative/local approval for this exact child preparation role, require an adult present, and prohibit retrieval after wind/rain or evacuation begins. |
| `typ_home_3_window1`, `typ_home_4_window2` | `before`; child operates two storm-shutter latches. | Closest boundaries: `TYP-BEF-001`, `TYP-BEF-002` | `EVIDENCE_GAP`. Obtain household/child-safety review for the exact latch task. It must occur before hazardous wind/rain and under adult supervision; never tell a learner to approach glass during the storm. |
| `typ_home_5_center` | `during`; storm active; approved indoor shelter; stay in center away from windows. | `TYP-DUR-001` | `READY`. An authenticated evacuation order must override sheltering through `TYP-BEF-005`. |
| `typ_home_6_bottle` | `after`; classify broken glass as danger, refuse touching, report to adult. | `TYP-AFT-001`, `TYP-AFT-002`, `TYP-AFT-006` | `READY` only after official clearance; “do not touch/report” is aligned. |
| `typ_home_7_wire` | `after`; classify a downed wire as danger, remain away, report. | `TYP-AFT-001`, `TYP-AFT-002`, `TYP-AFT-006`; electrical boundary `TYP-DUR-005` | `READY` only after official clearance and at a distance. |
| `typ_home_8_branch` | `after`; child picks up the configured harmless branch prop and puts it in a bin. | `TYP-AFT-002`, `TYP-AFT-006` | `SCENARIO_BOUND`. Retain the classification/cleanup task after the simulated all-clear. The LLM must not generalize it into handling real storm debris, damaged trees, wires, or uncleared objects. |
| `typ_home_9_toy` | `after`; child picks up an outdoor toy and bins it. | `TYP-AFT-001`, `TYP-AFT-002`, `TYP-AFT-006` | `LOCAL_REVIEW`. Do not allow cleanup until authenticated clearance and an adult has confirmed the object/area is safe; otherwise replace with report-and-wait. |

## Typhoon School

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `typ_sch_1_books`, `typ_sch_2_chair`, `typ_sch_3_window1`, `typ_sch_4_window2` | `before`; child moves books/chair and operates window shutters as rain begins. | `TYP-BEF-003`, with general information boundary `TYP-BEF-001` | `LOCAL_REVIEW` plus `EVIDENCE_GAP` for the exact child tasks. The school must approve the objects, timing, supervision, and stopping condition. No task may continue once wind/rain makes window proximity unsafe or an evacuation order is active. |
| `typ_sch_5_center`, `typ_sch_6_listen` | `during`; storm active; approved school safe area; stay away from windows and follow teacher. | `TYP-DUR-001`, `TYP-DUR-002` | `READY`. |
| `typ_sch_7_flood` | `after`; learner follows the configured green raised-edge route through the corridor while avoiding the deeper red zone. | `TYP-DUR-004`; flood-depth conflict `CF-005` | `SCENARIO_BOUND`. Retain the implemented route-choice exercise. The LLM must refer to the scenario-approved marked path, not claim that apparently shallow real floodwater is generally safe to cross. |

## Typhoon Outdoors

| Unity task ID(s) | Phase and trusted context meaning | Candidate corpus grounding | Status and required treatment |
|---|---|---|---|
| `typ_out_1_sky` | `before`; learner observes dark clouds as an educational cue. | `TYP-BEF-001`, `TYP-BEF-004` | `LOCAL_REVIEW`. The LLM must state that visual cues are not the current official warning; authenticated PAGASA/LGU/school/guardian information controls action. |
| `typ_out_2_warning` | `before`; learner approaches a configured warning post and receives an authenticated scenario warning to move early. | `TYP-BEF-001`, `TYP-BEF-004`, and `TYP-BEF-005` if it is an evacuation order | `LOCAL_REVIEW`. Cue identity and meaning must be trusted configuration, never inferred from audio/transcript. |
| `typ_out_3_high` | `during`; rising water; dry approved route to higher/sturdy shelter; do not approach drainage/floodwater. | `TYP-DUR-003`, `TYP-DUR-004`, `TYP-DUR-006` | `READY` if a responsible adult is present and the path remains dry/approved. Timer expiry may retry the simulation but must never imply real water is reversible. |
| `typ_out_4_evac` | `after`; official clearance plus approved dry route around floodwater and downed lines to configured center/shelter. | `TYP-AFT-001`, `TYP-AFT-002`, `TYP-AFT-005`, `TYP-DUR-004`, `TYP-DUR-005` | `LOCAL_REVIEW`. Require `official_clearance_received=true`; the route and center must be authenticated scenario configuration. |

## Scenario-bound review notes

| ID | Severity | Mission/task | Finding | Required disposition |
|---|---|---|---|---|
| `UXC-001` | Critical | Fire Home tasks 2–3 | Simulated preparation props differ from the corpus's conservative real-fire child boundary. | Keep the task scenario-bound; test that the LLM never generalizes it to approaching an active real fire or hot appliance. |
| `UXC-002` | Critical | Typhoon School task 7 | Configured raised-edge route exists beside simulated water, while the general corpus prohibits floodwater entry at any depth. | Keep the task scenario-bound; test that the LLM refers only to the marked VR route and never claims shallow real floodwater is safe. |
| `UXC-003` | High | Fire School task 3 | Immediately available cloth prop differs from guidance not to delay evacuation to find/wet a cloth. | Keep the task scenario-bound; test that generation never recommends searching for or wetting a cloth. |
| `UXC-004` | High | Typhoon Home task 8 | Harmless cleanup prop differs from the corpus's uncleared-debris boundary. | Require simulated clearance in context and prevent generalization to real debris cleanup. |
| `UXC-005` | High | Earthquake Home tasks 1–4 | Lightweight training props are described narratively as heavy objects. | Keep the practice task but identify the objects as configured lightweight simulation props in trusted context. |
| `UXC-006` | Medium/High | Earthquake School task 5 | Book/bag head-cover action is not in the route card and may conflict with no-belongings guidance (`CF-003`). | External protocol and language review before RAG use. |
| `UXC-007` | Medium/High | Typhoon Home tasks 2–4; Typhoon School tasks 1–4 | Exact child preparation roles lack sufficiently specific approved card semantics. | Obtain authority/school/child-safety approval or convert to identify/report/assist-adult tasks. |
| `UXC-008` | Medium | Fire School task 2 | Child handles paper near a hot plate; current boundary favors staying away/reporting. | Prefer report-to-teacher; validate any revised handling task. |
| `UXC-009` | Medium | All school/outdoor routes and cues | Route, shelter, assembly, warning, alarm, and headcount values are still synthetic/local. | Keep outside embeddings; replace with versioned school/scene configuration after approval. |

## RAG construction rules derived from this crosswalk

1. Build retrieval metadata from the trusted Unity state and this mapping, not
   from the learner's question alone.
2. Retrieve only curated card semantics and source references. Storyboard prose
   may describe the scene to the model but may not serve as factual safety
   evidence.
3. Keep every `SCENARIO_BOUND` task available to the LLM only when its exact
   trusted Unity state is active. Store it as scenario instruction metadata,
   not as context-free general safety evidence.
4. For `LOCAL_REVIEW` states, never embed school route names, alarm meanings,
   assembly geometry, live route status, or authority decisions. Send them as
   trusted structured context only.
5. The LLM may generate wording, but required/prohibited actions come from the
   retrieved cards. Post-generation validation must reject contradictions.
6. When a scenario-bound task and general corpus use different boundaries,
   label both roles explicitly in the prompt: the storyboard controls the
   current VR action, while the corpus controls what may be generalized beyond
   that simulated state.
7. Preserve the storyboard's gentle corrective loop, but corrections must be
   grounded in an eligible card.

## Recommended implementation sequence

1. Encode `UXC-001` through `UXC-005` as scenario-bound generation tests so the
   current missions remain usable without unsafe generalization.
2. Create `unity-earthquake-outdoors-v1` first as the cleanest small contract,
   then `unity-earthquake-home-v1` after its preparation-task decision.
3. Replace or reconcile the existing school-earthquake contract against the
   actual nine-task Unity flow.
4. Create the remaining fire and typhoon contracts with explicit
   `active_simulation_instruction` metadata for scenario-bound tasks.
5. Generate RAG validation cases from `READY` states first. Add
   `LOCAL_REVIEW` and `SCENARIO_BOUND` states as development cases with tests
   that preserve their exact VR context.

## Acceptance criteria for the next phase

- Every implemented Unity task appears in this crosswalk.
- Every referenced protocol ID exists in `corpus/protocol_cards.jsonl`.
- No `NEEDS_CURRENT_SOURCE` outdoor-fire card is required by an implemented
  mission because Fire Outdoors was cut.
- Every `SCENARIO_BOUND` task is available as an active simulation instruction
  and has a test preventing context-free real-world generalization.
- Mission contracts use actual Unity task/event IDs or a documented one-to-one
  state mapping.
- The same question asked in different mapped states retrieves different
  evidence when the safety meaning changes.
