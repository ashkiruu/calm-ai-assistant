# CALM Evidence Derivation Policy

Version: 1.0  
Scope: fire, earthquake, typhoon, and directly related flood conditions  
Target learner: elementary learner, with Grade 4 as the UAT population  

## Core decision

A PDF is not rejected merely because it was written for adults, responders,
school administrators, or engineers. Each claim is evaluated separately for
authority, relevance, currency, role, context, and safe transferability.

Original PDFs remain immutable evidence. CALM never edits an original source
and never embeds a raw PDF paragraph as learner guidance.

## Evidence layers

Every retained claim must be assigned to at least one layer:

1. `LEARNER_DERIVABLE` - an authoritative operational fact can be rewritten as
   an elementary learner action without changing its safety meaning.
2. `DETERMINISTIC_SYSTEM_RULE` - the fact controls a VR guard, state
   transition, action block, priority, or safe default. It is not selected by
   semantic similarity or model judgment.
3. `ADULT_HANDOFF_OR_DASHBOARD` - the fact belongs to a teacher, guardian,
   school administrator, DRRMO, BFP officer, or responder. A learner response
   may identify the responsible adult but must not transfer the adult task to
   the child.
4. `SCENARIO_DESIGN_REFERENCE` - the fact constrains the Unity scene, alarm,
   exit, route, assembly, safe-room, headcount, reunification, or monitoring
   workflow.
5. `POLICY_OR_THESIS_BACKGROUND` - the fact supports governance, rationale, or
   manuscript discussion but is not runtime guidance.
6. `EXCLUDED` - the claim is irrelevant, duplicated, stale without a safe use,
   contradictory without resolution, unsafe for the learner, or outside the
   current hazards.

## Allowed transformations

The derivation process may:

- shorten sentences and replace technical wording with familiar words;
- split one adult paragraph into atomic context-specific cards;
- author equivalent English, Filipino, and Taglish forms;
- convert an adult responsibility into a learner boundary and handoff;
- convert an engineering or administrative requirement into a VR or dashboard
  constraint; and
- omit authors, acknowledgements, static contacts, legal boilerplate,
  directories, and unrelated sections while retaining provenance.

Examples:

| Source statement type | Valid CALM transformation |
|---|---|
| Adult turns off electricity or LPG | Learner does not touch controls and reports the hazard to an adult. |
| Trained person uses an extinguisher | Learner alerts, evacuates, and stays out; the extinguisher action is blocked. |
| School establishes an assembly point | VR uses the locally approved assembly-point ID; the assistant never invents the location. |
| School conducts headcount | Learner stays with the class and answers roll call; staff operate the dashboard workflow. |
| Building code requires usable exits | Scenario designer verifies the route; the learner follows the marked approved exit. |

## Prohibited transformations

CALM must not:

- change a condition, negation, timing rule, action order, or hazard threshold;
- turn an adult, trained-person, or professional action into a learner duty;
- simplify a warning until it implies that a dangerous action is safe;
- combine instructions from different hazards, phases, settings, or actors;
- infer a school alarm, route, safe room, shelter, assembly point, or
  reunification location from a national PDF;
- treat an old warning scale, contact number, or plan as current;
- use an adult source to override a current specialist or local protocol; or
- claim external approval merely because an official document was cited.

## Required derivation record

Before a claim can support a protocol card, record:

- source ID, PDF page, and extracted line or verified visual region;
- issuing authority, publication year when known, and source hash;
- source actor and intended audience;
- applicable hazard, phase, setting, and learner context;
- evidence layer and transformation type;
- immutable safety meaning;
- proposed child-safe semantic form;
- prohibited actions and adult handoff;
- currency, local-configuration, conflict, and reviewer gates; and
- linked protocol card and validation cases.

## Runtime gate

Only the derived protocol card can enter learner retrieval, and only after the
existing lifecycle reaches `RUNTIME_APPROVED`. The source PDF, raw extracted
lines, adult-only material, technical tables, and background policy remain
outside the learner vector index.

This means that an adult or technical PDF can be valuable to CALM without ever
being directly retrievable by a Grade 4 learner.
