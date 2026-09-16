# Local model benchmark

Generated 2026-09-16 from `tests\fixtures\scope_eval.jsonl`.

Every check below is a rule the system prompt actually states, checked
deterministically. No model judges another model.

## Compliance

| Check | qwen2.5:3b |
|---|---|
| Scope routed correctly | 44/44 (100%) |
| No internal terms leaked | 44/44 (100%) |
| Within 45-word cap | 27/29 (93%) |
| At most 3 sentences | 26/29 (89%) |
| Answered in asked locale | 35/44 (79%) |
| Evidence matches hazard | 44/44 (100%) |
| **Overall** | **94%** |

The word-cap and sentence-cap rules are addressed to the model, so
they are scored only on generated answers. The remaining checks apply
to every reply, including the deterministic ones.

## Latency

Warm, GPU-resident; model load excluded.

| Metric | qwen2.5:3b |
|---|---|
| Median | 681 ms |
| p90 | 933 ms |
| Answers generated | 29/44 |

## Rule violations

### qwen2.5:3b

- **Safe ba ako dito?** (`fire_home_5_exit`, taglish-PH)
  - answer: Stay low and follow the configured safe arrows out through the available exit.
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
- **Ano ang gagawin after ng sunog?** (`fire_home_4_low`, taglish-PH)
  - answer: Get low below the simulated smoke layer and stay there for two seconds while the task confirms your position.
  - failed: correct_locale
- **Paano maghanda bago dumating ang bagyo?** (`typ_sch_6_listen`, fil-PH)
  - answer: First, stay calm in the approved safe area. Next, keep away from windows and glass. Then, listen to the teacher, guardian, or authenticated update.
  - failed: correct_locale
- **Paano kung may sunog dito?** (`eq_home_1_spot`, taglish-PH)
  - answer: That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is about a different emergency. That is.
  - failed: correct_locale, within_word_cap, within_sentence_cap
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: That is about a different emergency. That is about a different emergency. That is about a different emergency.
  - failed: correct_locale
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency. In this simulation, stay calm in the approved safe area. Keep away from windows and glass. Listen to the teacher, guardian, or authenticated update.
  - failed: correct_locale, within_sentence_cap
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale
