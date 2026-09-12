# KALMA learner-agency policy

## Purpose

The assistant must help Grade 4 learners recognise the current situation and
perform the safe action they can take, rather than making “find a teacher or
guardian” the default answer. This directly supports the manuscript objective
of practising independent situational decision-making without external
facilitator commands.

Independence does not mean pretending that a child has authority to choose an
unverified evacuation route, re-enter a structure, perform rescue, handle
medicine or utilities, or fight a fire. KALMA distinguishes immediate learner
agency from genuinely adult-controlled decisions.

## Answer hierarchy

Every on-task answer follows this order:

1. **Act now:** state the current self-protection or configured practice action.
2. **Avoid:** add a relevant prohibited action or real-world boundary when useful.
3. **Handoff:** mention an adult or responder only for the part that requires
   adult authority, equipment, training, or verified local information.

Finding an adult must not become a prerequisite for dropping, covering and
holding; staying low and exiting on the configured route; moving away from
glass, smoke, floodwater, wires, or falling hazards; remaining in an approved
safe zone; or completing a harmless configured VR-prop interaction.

## Scenario-bound evidence

The crosswalk separates two facts that previously conflicted:

- `active_simulation_instruction` is the exact action the learner can perform
  in the current trusted Unity task.
- curated protocol evidence supplies the real-world boundary and prohibited
  actions.

For controlled props, KALMA receives the task action and guardrails but does not
receive a real-heavy-object or active-fire adult handoff as if it were the
current procedure. Optional `practice_steps` provide trusted controller-level
instructions for “How?” follow-ups.

Example for `eq_home_4_picture`:

- “What should I do?” -> move the configured lightweight picture to the mat.
- “How?” -> grip the prop, move it over the mat, and release it.
- Real-world boundary -> do not climb or move a real heavy/hanging object.

## Authority that remains intentionally external

KALMA must retain teacher, guardian, responder, or official authority when the
trusted task or evidence requires it, including:

- school evacuation orders, authenticated routes, headcount, and reunification;
- rescue, firefighting, medical treatment, utilities, structural clearance,
  and re-entry;
- live PAGASA/LGU/school alerts that the local service cannot authenticate; and
- handling real heavy furniture, live flame, electrical hazards, or uncleared
  debris.

The assistant still leads with any supported self-protection action before the
handoff: move away, evacuate through the already approved exit, stay low, avoid
the hazard, or remain at the safe point.

## Regression expectations

- “Now/ngayon” and “next/susunod” refer to the active dialogue/task and do not
  invent a `during` or `after` disaster phase.
- A controlled practice task cannot be replaced by contradictory real-world
  adult-handoff steps.
- “What?” and “How?” use separate task instruction and interaction-step fields.
- A task that explicitly names teacher guidance keeps it.
- Learner speech never authorizes movement or changes mission state.

## Project-wide verification

The policy is applied by the shared RAG prompt and Unity crosswalk, not by a
single scenario-specific response. The repeatable learner-agency audit exercises
all 55 implemented task IDs across Earthquake, Fire, and Typhoon missions in
Home, School, and Outdoor settings. For each task it asks a normal next-action
question, an explicitly-alone question, and a contextual “How?” follow-up.

The 2026-08-29 live-model run evaluated 165 answers and reported zero unresolved
findings. It checked task grounding, current-task scope, action-first ordering,
adult-dependency replacement, internal-metadata leakage, subtitle length, and
configured interaction steps. The machine-readable evidence is in
`reports/learner_agency_audit_2026-08-29.json`; rerun it with:

```powershell
.\venv\Scripts\python.exe -m scripts.audit_learner_agency --output reports\learner_agency_audit_2026-08-29.json
```

This is regression evidence for the implemented scenarios, not a substitute for
child-safety, language, school, or disaster-authority review.

The model produced 164 of those final answers directly. One Fire Home posture
answer omitted the configured two-second hold and tried to advance to the exit;
the shared grounding guard replaced it with the complete trusted crouch-and-hold
mechanic. The same guard rejects an unnecessary adult handoff on any
learner-executable `scenario_bound` or `evidence_gap` task.
