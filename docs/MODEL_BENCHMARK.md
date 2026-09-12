# Local model benchmark

Generated 2026-08-28 from `tests\fixtures\scope_eval.jsonl`.

Every check below is a rule the system prompt actually states, checked
deterministically. No model judges another model.

## Compliance

| Check | qwen2.5:3b |
|---|---|
| Scope routed correctly | 44/44 (100%) |
| No internal terms leaked | 44/44 (100%) |
| Within 30-word cap | 29/29 (100%) |
| Single sentence | 23/29 (79%) |
| Answered in asked locale | 40/44 (90%) |
| Evidence matches hazard | 44/44 (100%) |
| **Overall** | **95%** |

The word-cap and single-sentence rules are addressed to the model, so
they are scored only on generated answers. The remaining checks apply
to every reply, including the deterministic ones.

## Latency

Warm, GPU-resident; model load excluded.

| Metric | qwen2.5:3b |
|---|---|
| Median | 604 ms |
| p90 | 978 ms |
| Answers generated | 29/44 |

## Rule violations

### qwen2.5:3b

- **Safe ba ako dito?** (`fire_home_5_exit`, taglish-PH)
  - answer: Safe ba ako dito? Magandang gawin ang approved safe exit at dumiretso sa meeting point.
  - failed: single_sentence
- **Paano kung may sunog dito?** (`eq_home_1_spot`, taglish-PH)
  - answer: That is about a different emergency. In this simulation, follow for an earthquake.
  - failed: correct_locale, single_sentence
- **What if there is a fire at school?** (`eq_sch_1_map`, en-PH)
  - answer: That is about a different emergency. This evidence is for fire evacuation.
  - failed: single_sentence
- **Paano kung may lindol habang nasa school?** (`fire_sch_2_paper`, taglish-PH)
  - answer: That is about a different emergency. Use the nearest approved cover, at hintaying huminto ang shaking.
  - failed: single_sentence
- **Paano kung may bagyo?** (`eq_home_3_box`, fil-PH)
  - answer: That is about a different emergency.
  - failed: correct_locale
- **Paano kung may sunog sa bahay?** (`typ_home_1_pack`, fil-PH)
  - answer: That is about a different emergency. Magbabala sa nakatatanda at gamitin ang tamang ligtas na labasan o safe zone.
  - failed: single_sentence
- **Ano kung may lindol ngayon?** (`typ_sch_1_books`, taglish-PH)
  - answer: That is about a different emergency.
  - failed: correct_locale
- **Do earthquakes happen a lot?** (`typ_home_1_pack`, en-PH)
  - answer: That is about a different emergency. Earthquakes are not mentioned in the provided context.
  - failed: single_sentence
- **Pwede mo ba akong bilhan ng laruan?** (`typ_sch_1_books`, taglish-PH)
  - answer: CALM helps with disaster preparation and emergency-response learning. Ask a safety question.
  - failed: correct_locale
