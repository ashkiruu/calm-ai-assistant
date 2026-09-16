# Local model benchmark

Generated 2026-09-16 from `tests\fixtures\scope_eval.jsonl`.

Every check below is a rule the system prompt actually states, checked
deterministically. No model judges another model.

## Compliance

| Check | ollama:qwen2.5:3b | google/gemma-4-31b-it | nousresearch/hermes-4-405b | deepseek/deepseek-v4-pro | inclusionai/ling-3.0-flash-vl:free | nex-agi/nex-n2.5-pro:free |
|---|---|---|---|---|---|---|
| Scope routed correctly | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) |
| No internal terms leaked | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) |
| Within 45-word cap | 26/29 (89%) | 29/29 (100%) | 28/29 (96%) | 19/19 (100%) | 17/19 (89%) | 23/23 (100%) |
| At most 3 sentences | 25/29 (86%) | 24/29 (82%) | 25/29 (86%) | 19/19 (100%) | 16/19 (84%) | 20/23 (86%) |
| Answered in asked locale | 36/44 (81%) | 39/44 (88%) | 39/44 (88%) | 43/44 (97%) | 42/44 (95%) | 41/44 (93%) |
| Evidence matches hazard | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) | 44/44 (100%) |
| **Overall** | **93%** | **95%** | **95%** | **99%** | **96%** | **97%** |
| *Answers actually generated* | *29/44* | *29/44* | *29/44* | *19/44* | *19/44* | *23/44* |

The word-cap and sentence-cap rules are addressed to the model, so
they are scored only on generated answers. The remaining checks apply
to every reply, including the deterministic ones.

**Read the generated row before the overall row.** Every question the
model does not answer falls back to reviewed deterministic text, and
that text passes scope, evidence and leaked-term checks by
construction. A model answering half the questions is therefore scored
half on the pipeline, which flatters it. A model answering none is
rejected outright rather than reported.

## Latency

**Providers differ in this run, so these are NOT comparable.** A local
figure is compute only; a hosted figure includes network round-trip and
the provider's own queueing. Compare compliance across providers, and
latency only within one.

| Metric | ollama:qwen2.5:3b | google/gemma-4-31b-it | nousresearch/hermes-4-405b | deepseek/deepseek-v4-pro | inclusionai/ling-3.0-flash-vl:free | nex-agi/nex-n2.5-pro:free |
|---|---|---|---|---|---|---|
| Provider | ollama | openrouter | openrouter | openrouter | openrouter | openrouter |
| Median | 645 ms | 788 ms | 1380 ms | 9196 ms | 5338 ms | 10226 ms |
| p90 | 892 ms | 1311 ms | 1885 ms | 16580 ms | 8965 ms | 19292 ms |
| Answers generated | 29/44 | 29/44 | 29/44 | 19/44 | 19/44 | 23/44 |

## Rule violations

### ollama:qwen2.5:3b

- **Ano ang gagawin ko?** (`eq_sch_4_dch`, fil-PH)
  - answer: Get under the configured learner desk, drop, cover, and hold until shaking stops.
  - failed: correct_locale
- **Safe ba ako dito?** (`fire_home_5_exit`, taglish-PH)
  - answer: Stay low and follow the configured safe arrows out through the available exit.
  - failed: correct_locale
- **Ligtas ba ang lugar na ito?** (`typ_sch_5_center`, fil-PH)
  - answer: Move to the configured center safe zone away from classroom windows.
  - failed: correct_locale
- **How do I prepare for a typhoon?** (`typ_home_1_pack`, en-PH)
  - answer: First, Pack the five configured child-safe preparedness items into the training go-bag. Next, Know the family route and meeting place. Then, With a guardian check water, ready-to-eat food, clothing, flashlight, whistle, radio, rain gear, blanket, hygiene items, and a comfort item. Keep the bag accessible without blocking an exit.
  - failed: within_word_cap, within_sentence_cap
- **Paano maghanda bago ang bagyo?** (`typ_sch_1_books`, fil-PH)
  - answer: First, move the configured training book stack from the floor to the shelf.
  - failed: correct_locale
- **Anong exit ang gagamitin ko?** (`fire_sch_1_exit`, taglish-PH)
  - answer: Move the configured lightweight box prop from the fire exit to the glowing clear spot.
  - failed: correct_locale
- **Paano maghanda bago dumating ang bagyo?** (`typ_sch_6_listen`, fil-PH)
  - answer: First, stay calm in the approved safe area. Next, keep away from windows and glass. Then, listen to the teacher, guardian, or authenticated update.
  - failed: correct_locale
- **How should I get ready for an earthquake?** (`eq_home_7_out`, en-PH)
  - answer: First, identify a sturdy cover place. Next, know the approved exit route and assembly area. Then, practise the drill with an adult or teacher. Then, identify the scenario-approved open area. Then, notice buildings, trees, posts, power lines, and glass that may fall. Then, listen to the guardian. Then, use the approved safe route. Then, walk to the family meeting place and stay together. Then, move away from the unsafe object. Then, tell a teacher or guardian what and where it is.
  - failed: within_word_cap, within_sentence_cap
- **What if there is a fire at school?** (`eq_sch_1_map`, en-PH)
  - answer: That is about a different emergency. That is about a fire. That is about a different emergency. That is about a fire. That is about a different emergency. That is about a fire. Stay at the meeting point for headcount and tell the adult in charge if someone is missing.
  - failed: within_word_cap, within_sentence_cap
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency. In this simulation, first, stay calm in the approved safe area. Next, keep away from windows and glass. Then, listen to the teacher, guardian, or authenticated update.
  - failed: correct_locale, within_sentence_cap
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale

### google/gemma-4-31b-it

- **How do I prepare for a typhoon?** (`typ_home_1_pack`, en-PH)
  - answer: First, pack the five configured child-safe preparedness items into the training go-bag. Next, know the family route and meeting place. Then, with a guardian check supplies like water and food. Keep the bag accessible without blocking an exit.
  - failed: within_sentence_cap
- **Paano kung may sunog dito?** (`eq_home_1_spot`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, go to the assigned meeting or assembly point. Next, stay with the family or class. Then, answer the headcount. Report a missing person to the adult in charge.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, stop moving toward the exit. Next, use the nearest approved cover. Then, wait until shaking stops.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency. In this simulation, first, stay calm in the approved safe area. Next, keep away from windows and glass. Then, listen to the teacher, guardian, or beripikadong abiso.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may sunog sa bahay?** (`typ_home_1_pack`, fil-PH)
  - answer: That is about a different emergency. First, move away from the fire. Next, alert an adult or alarm if safely reachable. Then, use the approved safe exit or safe zone.
  - failed: correct_locale, within_sentence_cap
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale

### nousresearch/hermes-4-405b

- **How do I prepare for a typhoon?** (`typ_home_1_pack`, en-PH)
  - answer: First, pack the five configured child-safe preparedness items into the training go-bag. Next, know the family route and meeting place. Then, with a guardian check water, ready-to-eat food, clothing, flashlight, whistle, radio, rain gear, blanket, hygiene items, and a comfort item. Keep the bag accessible without blocking an exit.
  - failed: within_word_cap, within_sentence_cap
- **Paano kung may sunog dito?** (`eq_home_1_spot`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, go to the assigned meeting or assembly point. Next, stay with the family or class. Then, answer the headcount. Report a missing person to the adult in charge.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, stop moving toward the exit. Next, use the nearest approved cover. Then, wait until shaking stops.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency. In this simulation: First, stay calm in the approved safe area. Next, keep away from windows and glass. Then, listen to the teacher, guardian, or authenticated update.
  - failed: correct_locale, within_sentence_cap
- **Paano kung may sunog sa bahay?** (`typ_home_1_pack`, fil-PH)
  - answer: First, move away from the fire. Next, alert an adult or alarm if safely reachable. Then, use the approved safe exit or safe zone.
  - failed: correct_locale
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale

### deepseek/deepseek-v4-pro

- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale

### inclusionai/ling-3.0-flash-vl:free

- **What should I do now?** (`eq_home_6_dch`, en-PH)
  - answer: Get under the configured sturdy table, drop, cover, and hold until shaking stops. Drop to hands and knees, take cover under the sturdy desk, protect your head and neck, and stay there until the shaking stops. Do not run to an exit or use an elevator.
  - failed: within_word_cap
- **How do I prepare for a typhoon?** (`typ_home_1_pack`, en-PH)
  - answer: First, pack the five configured child-safe preparedness items into the training go-bag. Next, know the family route and meeting place. Then, with a guardian check water, food, clothing, flashlight, whistle, radio, rain gear, blanket, hygiene items, and a comfort item. Keep the bag accessible without blocking an exit.
  - failed: within_word_cap, within_sentence_cap
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: In this simulation, that is about a different emergency. First, stop moving toward the exit. Next, use the nearest approved cover. Then, wait until shaking stops.
  - failed: correct_locale, within_sentence_cap
- **What if there is a flood?** (`fire_sch_1_exit`, en-PH)
  - answer: That is about a different emergency. Stay with your class and use the dry approved route to the higher safe area. Do not enter floodwater. Signal your location and wait for responder instructions.
  - failed: within_sentence_cap
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale

### nex-agi/nex-n2.5-pro:free

- **Safe ba ako dito?** (`fire_home_5_exit`, taglish-PH)
  - answer: Stay low and follow the configured safe arrows out through the
  - failed: correct_locale
- **Paano kung may sunog dito?** (`eq_home_1_spot`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, go to the assigned meeting or assembly point. Next, stay with your family or class and answer the headcount; then, report a missing person to the adult in charge.
  - failed: correct_locale
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, first, Stop moving toward the exit. Next, use the nearest approved cover. Then, hintaying huminto ang shaking.
  - failed: within_sentence_cap
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency. In this simulation, first, maging mahinahon sa approved safe area. Next, keep away from windows and glass. Then, makinig sa guro, tagapag-alaga, o beripikadong abiso.
  - failed: within_sentence_cap
- **Paano kung may sunog sa bahay?** (`typ_home_1_pack`, fil-PH)
  - answer: That is about a different emergency. First, lumayo sa apoy. Next, magbala sa nakatatanda o alarma kung ligtas na maabot. Then, gamitin ang tamang ligtas na labasan o safe zone.
  - failed: within_sentence_cap
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale
