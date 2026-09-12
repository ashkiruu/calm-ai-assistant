# CALM Corpus Policy

Version: 1.0  
Scope: Grade 4 prototype, understandable to Grades 3–6  
Jurisdiction: Philippines  
Hazards: fire, earthquake, typhoon and directly related flood conditions

## 1. Purpose

CALM teaches safe emergency choices inside a scenario-based VR simulation. The
knowledge base must answer a learner's disaster-preparedness question while
respecting the actual VR hazard, phase, setting, observed action, and authority
instruction.

The knowledge base is not a live warning service, medical service, emergency
dispatcher, or substitute for teachers, guardians, responders, PAGASA,
PHIVOLCS, BFP, DepEd, OCD, or the local DRRMO.

## 2. Source priority

When sources differ, use this order:

1. A written protocol approved for the deployment by the relevant local DRRMO,
   school, and specialist authority.
2. Current Philippine specialist authorities: BFP for fire, PHIVOLCS for
   earthquake, PAGASA for weather and flood warnings, and DepEd DRRMS for
   school procedures.
3. OCD/NDRRMC and other Philippine national-government material.
4. UNICEF and other established child-safety organizations.
5. Peer-reviewed academic literature for design rationale, not operational
   commands.
6. Legacy or generic material only as background.

An old source is not automatically discarded, but an operational instruction
from it cannot override a current specialist source.

## 3. Immutable evidence and derived text

- Original PDFs are never edited.
- Rejected or superseded PDFs are moved to `documents/archive/`, not deleted.
- A source is not rejected only because its intended audience is older than
  Grade 4. Relevant adult, administrator, responder, legal, and engineering
  claims may be retained for role-gated derivation, deterministic system
  rules, dashboard behavior, scenario design, or thesis background.
- Every local PDF is identified by SHA-256 and page count.
- `raw_pages/` preserves page and line traceability.
- Author names, acknowledgements, addresses, static phone numbers, navigation,
  repeated headers and footers, legal boilerplate, and unrelated chapters are
  omitted from learner retrieval.
- Provenance is never removed. Each derived claim retains source ID, issuing
  authority, year when known, exact PDF page, URL when known, and file hash
  through the source registry.
- Only a reviewed derived protocol card may enter learner retrieval. Raw PDF
  paragraphs, adult-only actions, technical tables, and policy text never do.

The permitted transformations and evidence layers are defined in
`DERIVATION_POLICY.md`.

## 4. Unit of knowledge

One protocol card represents one decision or tightly coupled action sequence.
Raw PDF paragraphs are not vectorized as learner guidance.

Each card must define:

- hazard, phase, setting, learner role, and age band;
- the trusted VR or authority conditions that make it applicable;
- ordered actions and prohibited actions;
- deterministic trigger, failure, completion, and safe-default behavior;
- English, Filipino, and Taglish wording with semantic-equivalence review;
- page-level provenance and unresolved conflicts;
- lifecycle and reviewer approvals; and
- linked positive, negative, boundary, and adversarial tests.

## 5. Disposition labels

These are claim-level labels. A single PDF can contain several labels and can
support a non-learner layer even when none of its text is directly retrievable.

- `KEEP_EXACT`: preserve the approved operational meaning and action order.
- `SIMPLIFY`: preserve meaning while rewriting for Grades 3–6.
- `ADULT_ONLY`: useful for a teacher, guardian, responder, dashboard, or
  scenario designer; never present it as a learner task.
- `BACKGROUND_ONLY`: concepts or policy useful outside immediate runtime
  guidance.
- `CONFLICT_REVIEW`: quarantine until a qualified reviewer resolves it.
- `EXCLUDE`: do not place in any retrievable learner corpus.

## 6. Child-action boundary

CALM must never instruct a Grade 4 learner to:

- fight a real fire or operate a fire extinguisher;
- touch LPG, gas valves, circuit breakers, outlets, appliances, damaged wires,
  or utility controls;
- handle matches, lighters, candles, knives, medicines, chemicals, fuel, or
  water-purification tablets;
- enter or cross floodwater, a river, moving water, or a damaged structure;
- retrieve belongings or a go-bag when doing so delays evacuation;
- physically rescue, carry, or provide medical treatment to another person;
- inspect or repair a building, roof, tree, electrical system, or gas system;
- ignore an evacuation order, teacher, guardian, responder, or official
  warning; or
- depend on a damp cloth as protection from smoke or delay escape to find one.

The learner may alert an adult, activate an accessible alarm in an actual fire,
follow an approved route, move to an approved safe area, report an injury or
missing person, and perform a self-protective action such as
Drop–Cover–Hold On or Stop–Drop–Roll when its exact trigger is present.

## 7. Deterministic versus generative behavior

- `P0_CRITICAL`: VR state selects exact approved wording. The language model
  cannot paraphrase, suppress, reorder, or contradict it.
- `P1_IMPORTANT`: VR state selects the card; only a reviewed constrained
  rendering may be used.
- `P2_EDUCATIONAL`: grounded explanation or question answering may be
  generated from approved semantics.

Voice input cannot override trusted VR hazard, location, phase, alarm,
evacuation-order, or observed-action state. If context is missing or
contradictory, CALM asks one bounded clarification or gives a safe non-action
fallback.

An official evacuation order overrides generic “stay indoors” typhoon advice.
Active earthquake shaking normally locks evacuation instructions until shaking
stops. Any compound-hazard exception requires an explicit, expert-approved
deterministic rule.

## 8. Language and tone

- Use short sentences and familiar words.
- Give the immediate action before the explanation.
- Remain calm without minimizing danger.
- Do not shame, frighten, diagnose, promise safety, or invent certainty.
- Filipino and Taglish are authored and reviewed, not translated at runtime.
- Taglish must not weaken a prohibition or make timing ambiguous.
- All critical TTS strings must be tested with child speech and common
  Philippine accents.

## 9. Real-time and local information

The static corpus must not claim a current storm signal, earthquake status,
school suspension, evacuation order, safe route, shelter availability, hotline,
or building condition.

Those values require a separately authenticated live or locally maintained
source. Without it, CALM says it cannot check the current alert and directs the
learner to the teacher, guardian, responder, or official display.

## 10. Data minimization

The knowledge base stores documents and protocol metadata, not child identity.
Runtime telemetry should use a random session ID and the minimum event fields
needed for system evaluation.

Do not store a child's name, face/video, raw voice after transcription, exact
home address, phone number, contacts, medical details, free-form conversation
history, precise location outside the VR scene, or device identifiers unless a
separate reviewed requirement, consent process, retention period, and access
control explicitly authorize it.

## 11. Review lifecycle

`DRAFT → EVIDENCE_LINKED → ROLE_CONTEXT_CLASSIFIED → DOMAIN_APPROVED →
CHILD_SAFETY_APPROVED → LANGUAGE_EQUIVALENCE_APPROVED → VR_RULE_TESTED →
PILOT_APPROVED → RUNTIME_APPROVED`

Blocking states are `CONFLICT_HOLD`, `NEEDS_CURRENT_SOURCE`, `SUSPENDED`,
`SUPERSEDED`, and `RETIRED`.

Required reviewers:

- fire: BFP plus DepEd/local DRRMO for school implementation;
- earthquake: PHIVOLCS plus DepEd/local DRRMO;
- typhoon/flood: PAGASA plus DepEd/local DRRMO;
- all hazards: Grade 4 educator or child-safety reviewer, Filipino/Taglish
  reviewer, and VR implementation reviewer.

## 12. Acceptance criteria for Phase 1

Phase 1 passes only when:

- every local PDF has a hash, audit result, and reversible disposition;
- no exact duplicate remains in the active source folders;
- the 27 hazard × setting × phase bundles have at least one evidence-linked
  card or an explicit source gap;
- every learner card has three language packs and page-level provenance;
- every P0/P1 card is blocked from runtime until required approvals exist;
- conflicts and adult-only actions are machine-testable;
- all corpus validation tests pass; and
- the production index is built only from `RUNTIME_APPROVED` cards.
