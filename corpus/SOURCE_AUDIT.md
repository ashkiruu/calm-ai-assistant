# CALM Source Audit

Audit date: 2026-07-31  
Re-audit rule: judge claim authority, relevance, currency, role, context, and
safe derivability; do not reject a source merely because it targets adults

## Method

Every local PDF was:

1. hashed with SHA-256;
2. represented by one extracted JSON record per PDF page under `raw_pages/`;
3. OCR-processed when the native text layer was absent or nearly empty;
4. checked for repeated lines and exact-file duplication;
5. reviewed across the complete extracted page/line set;
6. visually checked on relevant and ambiguous pages; and
7. assigned both a source-level storage decision and claim-level evidence role.

The raw page records are immutable evidence, not retrieval chunks. Only
reviewed derived protocol cards may enter learner retrieval.

## Result

| Final group | Count | Meaning |
|---|---:|---|
| `documents/approved` | 5 | Strong source for selective evidence-linked learner derivation. |
| `documents/reference` | 11 | Controlled derivation, deterministic rules, dashboard/staff logic, scenario design, corroboration, or policy. |
| `documents/archive` | 4 | Duplicate, outside current scope, or legacy material that must not guide current operations. |

No PDF was permanently deleted. No raw PDF is approved for direct learner RAG.
The complete source-level decision is in
`reports/pdf_derivation_matrix.csv`; detailed findings are in
`reports/PDF_REAUDIT_2026-07-31.md`.

## Approved sources

### BFP Fire Safety for Children, Volume 1 (2024)

Keep visually verified narrative material on PDF pages 195-241, especially
pages 210-213, plus page 279. Safe claims include:

- do not play with matches, lighters, candles, stoves, or fire;
- alert a teacher or adult and use an accessible alarm only for an actual fire;
- evacuate immediately using the approved route;
- use stairs rather than elevators;
- stay low and crawl when smoke is present;
- Stop-Drop-Roll if clothing catches fire;
- go to the meeting or assembly point; and
- once outside, stay outside and report missing people.

Extinguisher lessons, suppression, live flame, pet rescue, and wet-cloth
claims are quarantined. Visual review confirmed unsafe or inconsistent quiz
answers on PDF page 243, so quiz and answer material on pages 202, 243, 284,
296, 304, and 322-325 is excluded pending a corrected BFP-reviewed bank.

### DepEd M7.2 Earthquake Preparedness IEC (2019)

PDF page 6 is the strongest learner-action page: identify falling hazards,
Drop-Cover-Hold On, remain protected until shaking stops, then evacuate
orderly without running, pushing, using an elevator, or approaching buildings,
trees, or power lines. Pages 1, 5, and 7 support school planning, scene logic,
reunification, and adult-managed preparation.

### OCD Disaster Preparedness Guidebook

Selectively derive pages 3-5, 7-8, 10-11. Split every claim by hazard, phase,
setting, and actor. Adult utility work, repair, suppression, rescue, medical
action, stale contacts, and unrelated hazards are excluded.

### UNICEF Philippines family guide (2021)

Selectively derive pages 3-13 for family plans, age-appropriate roles,
go-bags, warnings, evacuation, return clearance, earthquake protection,
aftershocks, and emotional check-ins. Adults retain custody of money, records,
medicine, matches, candles, and utilities.

### Project MAGHANDA Broadcasters' Manual (2022)

Selectively derive pages 9-10, 12-13, 23-24, 41-42, and 50-51. Pages 18 and
46-50 may support deterministic terminology after specialist review. Exclude
TPASS, cooking-oil/LPG wet-cloth actions, utility work, repair, first aid,
directories, static contacts, and any live alert inferred from the PDF.

## Reference sources

- **RA 10121:** statutory evidence for people-centered early warning,
  vulnerable groups, public information, evacuation, education, and national/
  local DRRM roles. It supplies no direct learner protocol.
- **National Disaster Preparedness Plan 2015-2028, Volume 1:** the local
  filename incorrectly says 2015-2018. Retain selected framework, scenario,
  IEC, EWS, evacuation, continuity, and M&E sections for architecture and
  dashboard design subject to currentness review.
- **DILG Memorandum Circular No. 2015-76:** review-only reference for ICS,
  early warning, evacuation centers, routes, drills, coordination, and local-
  configuration requirements. Current local protocols and signs control.
- **DepEd Order 033, s. 2021:** pages 4, 7-12, 16-18, and 25-29 inform learner
  role limits, accessibility, mapping, drills, reunification, EWS, and local
  flood markers. Most actions belong to schools and offices.
- **DepEd SDRRM Manual Book 1:** governance, localization, mapping, routes,
  warning, learning design, and review. Its hidden text layer duplicates
  adjacent pages, so it is never ingested wholesale.
- **PHIVOLCS Earthquake Drill Guide (2005):** alarm-to-headcount sequence.
  Doorway, door-handling, fixed timing/capacity, and go-bag rules are held for
  current review.
- **OCD Earthquake Preparedness leaflet:** corroborates the larger OCD guide;
  vehicle-exit, utilities, repair, first aid, and stale contacts are blocked.
- **DOE Typhoon brochure (2016):** background for official updates, calm,
  drills, windows, and authority-directed evacuation. Old categories and adult
  tasks are excluded.
- **BFP Fire Safety for Teenagers, Volume 2 (2024):** derivation-only reference
  for exits, wiring/overload, unattended cooking, open flame, and ignition
  hazard recognition. Correction, suppression, and live-fire work are adult-
  only or excluded.
- **BFP Fire Safety for Young Adults, Volume 3 (2024):** derivation-only
  reference for evacuation, alternate routes, accessibility, assembly,
  headcount, and no re-entry. Planning, rescue, suppression, and staff duties
  do not transfer to learners.
- **BFP Occupancy Guidelines, Volume II:** technical scenario reference for
  Unity layout, exits, alarms, signs, accessibility, drills, and dashboard
  checks; never learner dialogue.

## Archived sources

- Both DTI operations manuals remain outside scope; one is an exact
  byte-for-byte duplicate.
- NDRRMC Memorandum 54, s. 2020 is a COVID-era administrative source for a
  possible future compound-hazard module, not the current learner corpus.
- The 2009 Fire Code IRR is legacy because BFP published a revised RIRR in
  2019. It cannot establish a current learner or school rule.

Exact paths, hashes, URLs, and source statuses are in `source_registry.csv`.
Claim-level reasons are in `source_audit.csv`, and disagreements or unsafe
transformations are in `conflicts.csv`.
