# Plan: registering `tut_13_ask` ("Ask KALMA") in the backend

## The problem, exactly

Pressing the talk button in Unity's Tutorial Part 3 does nothing — no error, no
"listening" state, nothing. Root cause: `CalmPushToTalk.OnPressed` (Unity side)
checks `CalmAssistant.CanAskTask(taskId)` before it will even open the
microphone. That check is just:

```csharp
public bool CanAskTask(string taskId) =>
    !string.IsNullOrEmpty(taskId) && _knownTasks != null && _knownTasks.Contains(taskId);
```

`_knownTasks` comes from `GET /api/v1/unity/tasks` on the server, which is
built from `unity_crosswalk.data["missions"]` — i.e. from
`config/unity_scenario_crosswalk.v1.json`. The Tutorial's new task,
`tut_13_ask`, was added to the Unity project this session and was never added
to that file. So `CanAskTask("tut_13_ask")` is always `false`, and the whole
push-to-talk flow silently no-ops before it ever touches the microphone or the
model. This is a **data problem, not a Unity bug** — nothing on the Unity side
needs to change.

## The two files involved (both in `calm-ai-assistant`, not in CALM_VR)

1. **`config/unity_scenario_crosswalk.v1.json`** — maps a Unity `task_id` to a
   `scenario_id`, a `hazard`/`setting`/`phase`, and a list of `protocol_ids`.
   This is what `/api/v1/unity/tasks` serves back to Unity, and it's what
   makes a task "known."
2. **`corpus/protocol_cards.jsonl`** — the actual curated safety content each
   task is allowed to ground an answer in. Every card carries real source
   citations (`provenance.source_claims`, PDF page numbers) and a
   `review.required_approvals` list (PHIVOLCS, DepEd/DRRMO, child-safety,
   language, VR implementation reviewers). **This file is not something to
   invent new entries for casually** — a fabricated card would be an
   ungrounded "safety fact" with no real source behind it, which is exactly
   what this whole system exists to prevent.

## The schema constraint that makes this non-trivial

`calm_core/unity_crosswalk.py`'s validator (`validate_crosswalk`) requires,
for every task:
- a parent "mission" with one `hazard` (`earthquake` | `fire` | `typhoon` —
  no "general" option) and one `setting` (`home` | `school` | `outdoor`)
- one `phase` (`before` | `during` | `after` — no "practice" option)
- a non-empty `protocol_ids` list, where **every** referenced card's own
  `classification.hazard` must match the task's `hazard`, and its
  `classification.settings` must include the task's `setting`

In other words: the schema is built around scenario-bound tasks
("earthquake, at home, before phase"). `tut_13_ask` — "ask KALMA anything
about staying safe" — doesn't naturally belong to any one hazard, setting, or
phase. That's the actual design question to solve, not a bug to patch.

## Two ways to unblock it — pick one

### Option A — fast, zero new content, but narrows what KALMA can answer (recommended to ship first)

Add `tut_13_ask` as a new task entry, reusing **existing, already-approved**
protocol cards from ONE hazard (pick whichever fits the Tutorial context best
— `earthquake` is a reasonable default since Part 4 right before it is about
duck-cover-hold). This makes KALMA able to answer questions grounded in that
one hazard's existing evidence, which is a real limitation (a kid asking
about fire safety would get a scope-decline, not silence — check
`test_question_scope.py` for how out-of-scope questions are already handled
gracefully) but ships today with **no new safety citations to review**.

Template entry (add as its own object inside the `"missions"` array in
`config/unity_scenario_crosswalk.v1.json`):

```json
{
  "scene": "Tutorial",
  "scenario_id": "unity-tutorial-ask-v1",
  "storyboard": "docs/storyboard/00_Tutorial.md",
  "hazard": "earthquake",
  "setting": "home",
  "location_type": "indoors",
  "default_location_zone": "HOME_INTERIOR",
  "implemented_task_count": 1,
  "tasks": [
    {
      "task_id": "tut_13_ask",
      "phase": "before",
      "learner_action": "ask_open_safety_question",
      "active_simulation_instruction": "The learner may ask KALMA any question about staying safe during an earthquake.",
      "practice_steps": ["Hold the talk button.", "Ask a safety question.", "Let go and listen to the answer."],
      "protocol_ids": ["EQ-BEF-003"],
      "mapping_status": "scenario_bound",
      "required_trusted_flags": {"hazard_active": false, "unsafe_object_visible": false},
      "scope_constraint": "Tutorial practice only — answers are grounded in earthquake-preparedness evidence; the learner is not in a live earthquake mission."
    }
  ]
}
```

`EQ-BEF-003` is a real, already-existing card (used by `eq_home_1_spot`) — no
new corpus entry needed. Swap it for whichever existing card(s) you think fit
best; just keep every referenced card's `hazard`/`settings` matching what you
put above.

**After editing, validate before touching the server:**
```bash
cd calm-ai-assistant
python scripts/validate_unity_crosswalk.py
```
It should print `PASS`. If it says a Unity task is "missing from crosswalk"
or similar for `tut_13_ask`, note that its own regex
(`UNITY_TASK_PATTERN` in `calm_core/unity_crosswalk.py`) only checks
`eq_`/`fire_`/`typ_`-prefixed ids against the live Unity source, so a `tut_`
id won't be flagged either way — that check simply won't run for the
Tutorial, which is fine.

Restart the server, then confirm from Unity: `GET /api/v1/unity/tasks` should
now list `tut_13_ask`.

### Option B — the "actually general" fix, more work, do this after A ships

Give the Tutorial's ask-anything task a genuinely different retrieval path
instead of squeezing it into one hazard. That means a small code change, not
just a data entry:
- Add a new `hazard` value like `"general"` (or a new boolean flag on the
  task, e.g. `"general_qa": true`) that `unity_crosswalk.py`'s validator and
  `UnityScenarioCrosswalk.retrieval_plan()` treat specially: instead of
  requiring every `protocol_ids` entry to match one hazard, retrieve across
  **all three hazards'** already-approved cards and let the RAG layer
  (`calm_core/rag_chat.py`) pick the most relevant ones per question.
- This is the right long-term answer (matches "ask me anything about staying
  safe," not "ask me anything about earthquakes"), but it touches the
  validator, the crosswalk reader, and possibly `rag_chat.py`'s retrieval
  call — hand ChatGPT `calm_core/unity_crosswalk.py` and
  `calm_core/rag_chat.py` in full and ask it to add a `general` hazard
  category that pools retrieval across all approved cards, keeping every
  existing scenario-bound task's behavior unchanged. Run the full test suite
  after (`pytest tests/test_unity_crosswalk.py tests/test_question_scope.py
  tests/test_rag_chat.py`) since those specifically cover this contract.

## What NOT to do

Don't hand-write a brand-new `protocol_cards.jsonl` entry with invented
`provenance.source_claims` (fake PDF pages) or a `review.required_approvals`
list you mark complete — that's fabricating a safety citation, which is the
one thing this whole architecture is built to prevent. If Part 3 genuinely
needs new safety content no existing card covers, that's a real
content-curation task for your adviser/DRRMO contact, not something to
generate.
