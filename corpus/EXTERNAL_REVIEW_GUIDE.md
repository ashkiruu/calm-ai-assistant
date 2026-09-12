# CALM Protocol Review Guide

This review is a safety and correctness check of the AI assistant's source
corpus. It is not a pre-test/post-test and does not measure learner knowledge.
UAT remains a separate system-validation activity.

## Review packet

Reviewers need:

- `protocol_cards.jsonl` — full canonical records;
- `reports/review_queue.csv` — one review row per card;
- `reports/coverage_matrix.csv` — all 27 context bundles;
- `conflicts.csv` — disagreements and source gaps;
- `SOURCE_AUDIT.md` — source disposition; and
- `DERIVATION_POLICY.md` - allowed and prohibited transformations;
- `reports/pdf_derivation_matrix.csv` - one re-audit decision per local PDF;
- `reports/PDF_REAUDIT_2026-07-31.md` - detailed page-level findings; and
- the cited PDFs in `documents/approved` and `documents/reference`.

## What each reviewer checks

### Domain authority

- **BFP:** fire action, order, terminology, trapped-person behavior,
  extinguisher boundary, outdoor-fire gap, and emergency-call role.
- **PHIVOLCS:** earthquake action, indoor/outdoor distinction, shaking versus
  evacuation timing, aftershocks, damaged-building boundary, and any coastal
  secondary-hazard condition.
- **PAGASA:** typhoon/flood action, current warning terminology, floodwater
  boundary, shelter-versus-evacuation precedence, and what may be described
  without live data.
- **DepEd/local DRRMO/school:** actual alarms, routes, safe rooms, assembly and
  reunification points, headcount, authority cues, and compound-hazard rules.

### Grade 4 and child-safety reviewer

- The learner can understand the action on first hearing.
- The action does not transfer adult or professional responsibility.
- The response gives the immediate action first and does not overload or
  frighten.
- Any adult or professional source action became a child boundary, adult
  handoff, deterministic rule, dashboard duty, or scenario constraint; it was
  not silently transferred to the learner.
- The assistant never asks the learner to rescue, repair, diagnose, medicate,
  fight a fire, touch utilities, or enter floodwater or damage.

### Filipino and Taglish reviewer

- English, Filipino, and Taglish have the same meaning and action order.
- Negation and timing remain explicit.
- Taglish sounds natural for Philippine elementary learners but does not weaken
  safety language.
- TTS pronunciation is understandable for child listeners.

### VR implementation reviewer

- Every required context field is available from a trusted game state.
- P0 action selection is deterministic and does not depend on vector
  similarity or LLM judgment.
- Completion and prohibited actions are observable in the VR scene.
- Missing or contradictory state fails closed.
- Telemetry is minimized and contains no unnecessary child data.

## Allowed decisions

- `APPROVE`: semantics and all three language forms are acceptable.
- `APPROVE_WITH_EDIT`: reviewer supplies exact replacement wording or
  condition.
- `CONFLICT_HOLD`: qualified authorities or source evidence disagree.
- `NEEDS_LOCALIZATION`: national rule is valid but route, alarm, shelter, or
  authority is local.
- `REJECT`: unsafe, inaccurate, irrelevant, or unsuitable for the age group.

No card becomes `RUNTIME_APPROVED` from one person's approval. The complete
lifecycle in `CORPUS_POLICY.md` must be satisfied.

## Highest-priority questions

1. Does BFP approve CALM's conservative rule that a Grade 4 learner never
   operates an extinguisher in a real-event VR mission?
2. What exact trapped-child fire wording should replace or confirm
   `FIR-DUR-006`?
3. What BFP/local DRRMO protocol should cover outdoor or vegetation fire for
   before, during, and after states?
4. Does PHIVOLCS approve the indoor/outdoor and aftershock sequencing in the
   earthquake cards?
5. What local school rule resolves whether a go-bag is already carried or must
   be left during evacuation?
6. Does PAGASA approve the absolute learner boundary of never entering
   floodwater at any depth?
7. Which school alarms, safe rooms, exits, routes, assembly points, and
   reunification points will be represented in the actual deployment?
8. What deterministic precedence applies if fire and earthquake states overlap?
