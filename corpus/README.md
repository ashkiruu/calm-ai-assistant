# CALM Phase 1 Knowledge Base

This directory contains the traceable, child-safe source layer for the CALM
context-aware AI assistant. The unsafe raw-PDF prototype database has been
retired; runtime code now reads curated cards only.

## Curated artifacts and eventual production inputs

- `protocol_cards.jsonl` contains canonical learner-facing safety actions.
- `card_specs/` contains the editable reviewed source specifications used to
  rebuild those cards.
- `system_rules.json` contains cross-hazard safety and retrieval rules.
- `source_registry.csv` records provenance, authority, hash, disposition, and
  final file location.
- `source_audit.csv` records why each source was approved, restricted, or
  archived.
- `DERIVATION_POLICY.md` defines how adult, technical, administrative, and
  child sources may support separate learner, deterministic-rule, dashboard,
  scenario-design, and background layers.
- `reports/pdf_derivation_matrix.csv` and
  `reports/PDF_REAUDIT_2026-07-31.md` record the complete 20-PDF re-audit.
- `conflicts.csv` records source disagreements that must never silently enter
  retrieval.
- `validation_cases.jsonl` contains deterministic and adversarial test cases.
- `development_approval.json` defines the explicit non-production gate used for
  prototype engineering and VR integration tests.

The files under `raw_pages/` are evidence for reviewers. They are **not**
approved retrieval content.

## Review status

The current cards are a corpus-engineering baseline, not a claim of approval by
BFP, PHIVOLCS, PAGASA, DepEd, or a local DRRMO. All P0/P1 cards remain blocked
from production until their required domain, child-safety, language, and VR
reviews are recorded.

## Languages

Every learner-facing card carries:

- `en-PH` — Philippine English;
- `fil-PH` — Filipino; and
- `taglish-PH` — reviewed Taglish.

All three versions must preserve the same action order, conditions, negations,
and actor boundary. Runtime translation is not allowed for critical commands.

## Build and validation

From the project root:

```powershell
venv\Scripts\python.exe scripts\build_protocol_cards.py
venv\Scripts\python.exe scripts\build_retrieval_units.py
venv\Scripts\python.exe scripts\validate_corpus.py
```

The validator checks source references, schema fields, context coverage,
language completeness, prohibited child actions, review gates, and test-case
links. It writes a machine-readable report to
`corpus/reports/validation_report.json`.

## Retrieval boundary

Only cards whose lifecycle is `RUNTIME_APPROVED` may enter a production vector
index. `DRAFT`, `EVIDENCE_LINKED`, `CONFLICT_HOLD`, `NEEDS_CURRENT_SOURCE`,
`SUSPENDED`, `SUPERSEDED`, and `RETIRED` must fail closed.

See `CORPUS_POLICY.md` for the complete rules.
