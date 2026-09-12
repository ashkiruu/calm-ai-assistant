# Phase 1 Corpus Engineering Summary

Status: **internal validation passed; external safety approval pending**

## Completed

- 20 local PDFs, 2,336 pages, are hash-registered and line/page traceable.
- 31 low-text pages in the two official additions were OCR-processed; the
  previously scanned short sources were also OCR-processed.
- Five PDFs are approved for selective derivation.
- Eleven PDFs are retained for controlled derivation, policy, deterministic
  rules, dashboard/staff logic, scenario design, legacy review, or
  corroboration.
- Four PDFs are reversibly archived; none was deleted.
- The complete PDF set was re-audited under a derivability rule: audience age
  alone is not an exclusion, but no raw PDF is direct learner RAG.
- BFP Volumes 2 and 3 were recovered as derivation-only references, the BFP
  occupancy guide as a scenario-design reference, and RA 10121 plus the
  visually verified National Disaster Preparedness Plan 2015-2028 as policy
  references.
- One exact DTI duplicate is identified by SHA-256 and isolated.
- Unsafe/inconsistent BFP child-manual quiz pages are quarantined, removed
  from ordinary protocol evidence, and enforced by the corpus validator.
- Three official current web references were added for PAGASA TCWS, PAGASA
  flood safety, and current PHIVOLCS earthquake corroboration.
- 47 atomic protocol cards cover all 27 combinations of:
  `fire|earthquake|typhoon × home|school|outdoor × before|during|after`.
- Every card has authored English, Filipino, and Taglish, giving 141 language
  renderings.
- 26 critical cards require deterministic exact wording.
- 43 adversarial and integrity cases are defined.
- Sanitized review retrieval units contain no author names, acknowledgements,
  addresses, static contact details, raw PDF paragraphs, or legal/navigation
  boilerplate.
- The invalid original Chroma database is archived because it used the same raw
  PDF for all three hazards.

## Deliberate production gate

There are currently **zero** production retrieval units. This is intentional:
none of the safety cards has yet completed BFP/PHIVOLCS/PAGASA,
DepEd/local-DRRMO, child-safety, language-equivalence, VR-rule, pilot, and UAT
review.

`retrieval/review_candidate_units.jsonl` contains 141 non-production units for
engineering review. `retrieval/runtime_units.jsonl` remains empty and must stay
empty until cards reach `RUNTIME_APPROVED`.

For prototype development only, `development_approval.json` permits
`EVIDENCE_LINKED` cards while excluding source-gap and hold states. Every API
response discloses that this internal decision is not external or production
approval.

## Known source gaps

Three cards—outdoor fire before, during, and after—are conservative placeholders
marked `NEEDS_CURRENT_SOURCE`. They cannot be deployed until BFP and the local
DRRMO approve the exact scenario, route, and wording.

Additional local decisions are still required for:

- school alarms and authority cues;
- safe rooms, exits, routes, assembly points, and reunification;
- fire-plus-earthquake compound-hazard precedence;
- emergency calling in the actual deployment; and
- the school rule for go-bags during evacuation.

## Rebuild commands

```powershell
venv\Scripts\python.exe scripts\build_protocol_cards.py
venv\Scripts\python.exe scripts\build_retrieval_units.py
venv\Scripts\python.exe scripts\validate_corpus.py
```

The last command must report `PASS` before the corpus is handed to the next
stage.
