# CALM Complete PDF Re-audit

Audit date: 2026-07-31  
Scope: 20 local PDFs, 2,336 pages  
Decision basis: relevance and safe derivability, not source age band alone

## Result

The user's proposed approach is valid with one boundary: CALM may transform
the presentation and learner role, but it may not alter the source's safety
meaning, condition, timing, negation, or action order.

The revised disposition is:

| Storage group | PDFs | Meaning |
|---|---:|---|
| Approved | 5 | Strong sources for selective evidence-linked learner derivation. |
| Reference | 11 | Useful for controlled derivation, deterministic rules, dashboard/staff logic, scenario design, corroboration, or policy. |
| Archive | 4 | Duplicate, outside current scope, or legacy material that must not guide current operations. |

No PDF is directly eligible for learner RAG. Only an atomic, reviewed,
provenance-linked protocol card may enter learner retrieval. The machine-readable
decision for every PDF is in `pdf_derivation_matrix.csv`.

## Method

- Reconciled all 20 PDFs against `source_registry.csv` by SHA-256, byte size,
  page count, and final path.
- Checked the complete 2,336-record raw-page set and its extracted lines.
- Visually checked relevant and ambiguous pages, including image-only and
  layout-dependent material.
- Assigned useful content to learner derivation, deterministic VR rules,
  staff/dashboard logic, scenario design, or policy/background.
- Rejected source lines or visual regions that were unsafe, stale,
  contradictory, duplicated, irrelevant, or not transferable to a child.
- Preserved all originals; nothing was rewritten inside a source PDF.

## Approved sources

### BFP Fire Safety for Children, Volume 1 (2024)

Retain selected primary-school lessons, especially PDF pages 210-213 and 279,
for alarm/alert, immediate evacuation, low movement under smoke,
Stop-Drop-Roll, meeting-point, stay-out, and no-re-entry semantics.

Do not derive extinguisher operation, fire suppression, pet rescue, live-flame
activities, or quiz answer keys. Visual review confirmed that PDF page 243's
answer key marks "Use the stairs" as NO, "Fall and crawl" as YES, and breathing
through the nose as YES. The assessment pages are therefore quarantined rather
than trusted merely because the manual targets children.

### DepEd M7.2 Earthquake Preparedness IEC (2019)

PDF page 6 remains the strongest direct learner page for falling-hazard
recognition, Duck/Drop-Cover-Hold, post-shaking evacuation, no
running/pushing/elevator, and avoiding buildings, trees, and power lines.
Pages 1, 5, and 7 support planning, scene logic, and adult-managed preparation.

### OCD Disaster Preparedness Guidebook

Selectively derive pages 3-5, 7-8, 10-11. Split them by hazard, phase,
setting, and actor. Utilities, repair, suppression, rescue, first aid, stale
contacts, and unrelated hazards remain outside learner retrieval. The older
flood-depth threshold must not imply that shallow floodwater is safe.

### UNICEF Philippines family guide (2021)

Selectively derive pages 3-13 for age-appropriate family roles, routes,
reunion points, go-bags, official warnings, evacuation, return clearance,
earthquake protection, aftershocks, and emotional check-ins. Adults retain
custody of money, records, medicine, matches, candles, and utilities.

### Project MAGHANDA Broadcasters' Manual (2022)

Selectively derive pages 9-10, 12-13, 23-24, 41-42, and 50-51. Pages 18 and
46-50 may support deterministic warning and intensity terminology after
specialist review. It is a valuable
cross-hazard Filipino source, but adult instructions must be role-gated.
Exclude TPASS, cooking-oil wet-cloth suppression, approaching an LPG fire,
utility work, repairs, first aid, directories, and static contacts.

## Reclassified references

### BFP Fire Safety for Teenagers, Volume 2 (2024)

Reclassified from `WRONG_AUDIENCE` to `REFERENCE_DERIVATION_ONLY`. Pages 47-56
and 167-181 provide useful hazard-recognition and prevention evidence for
unblocked exits, damaged wiring, overloaded connections, unattended cooking,
open flame, and ignition sources.

The valid child transform is: move away, do not touch or repair, and tell an
adult. Suppression pages, wet-cloth cooking-fire advice, extinguisher lessons,
and live-fire exercises remain non-transferable.

### BFP Fire Safety for Young Adults, Volume 3 (2024)

Reclassified from `WRONG_AUDIENCE` to `REFERENCE_DERIVATION_ONLY`. Pages
109-132 and 409-426 support exit, alternate-route, smoke, stair, alarm,
assembly, accessibility, headcount, and no-re-entry logic.

Planning, sweeping, assistance, emergency calling, and headcount operation
remain staff/responder tasks. Document or pet retrieval, physical smoke drills,
damp-cloth advice, suppression, rescue, first aid, and advanced modules are not
learner actions.

### BFP Fire Safety Guidelines on Occupancies, Volume II

Reclassified to `REFERENCE_SCENARIO_DESIGN`. Pages 23-37 and 191 support Unity
layout and dashboard checks for exits, egress, alarm, signs, accessibility,
and drills. Engineering measurements, equipment operation, inspection, and
compliance workflows remain developer/professional metadata.

### Republic Act 10121

Retained as policy/reference evidence for people-centered early warning,
children and other vulnerable groups, public information, evacuation,
education, and the roles of DepEd and local DRRM structures. It supplies no
direct learner emergency command.

### National Disaster Preparedness Plan 2015-2028, Volume 1

The local filename incorrectly says 2015-2018; visual review of the cover
confirms **2015-2028**. Retain pages 13-15, 40-58, 59-79, and 96-99 for
risk-assessed planning, scenario phases, IEC, early warning, evacuation,
response readiness, continuity, and monitoring/dashboard design. Old
workplans, agency assignments, funding details, and live operational rules
require currentness review and must not become learner instructions.

### DILG Memorandum Circular No. 2015-76

Retain pages 1-4, with page 5 only as historical sign examples, for ICS,
early-warning, evacuation-center, route/map, drill, coordination, and local-
configuration requirements. Learners may follow a currently approved warning
or sign; they do not activate ICS, order evacuation, perform rescue, or operate
gauges. Current DILG/OCD, local DRRMO, school-plan, and sign validation is
required.

### DepEd Order 033, s. 2021

Retain pages 4, 7-12, 16-18, and 25-29 for the learner-role safety gate,
accessibility, hazard mapping, routes, EWS, drills, reunification, personal
safety, and locally calibrated flood markers. Maintenance, guy wires, pruning,
drainage, electrical shutoff, and office operations are adult/professional.
Never confuse school marker colors with PAGASA warning colors.

### DepEd SDRRM Manual Book 1

Retain pages 2, 10-11, 15-18, and 21-29 for governance, localization, hazard
mapping, routes, warning, learning design, review, and dashboard/scenario
requirements. The hidden text layer duplicates adjacent pages, so the source
must never be ingested wholesale.

### PHIVOLCS Earthquake Drill Guide (2005)

Retain pages 1-2 for the alarm-protect-wait-evacuate-assemble-headcount-
evaluate sequence. Quarantine doorway advice, door handling during shaking,
fixed timing/capacity assumptions, and the go-bag conflict. Current PHIVOLCS
and school validation is required.

### OCD Earthquake Preparedness leaflet

Retain pages 1-2 as corroboration for earthquake protection and preparation.
It substantially duplicates the larger OCD guide. Vehicle-exit, adult utility,
repair, first-aid, and stale-contact content remains blocked.

### DOE Disaster Preparedness: Typhoon (2016)

Retain page 2 only as background for monitoring official information,
remaining calm, drills, window safety, and following an evacuation order.
Exclude its obsolete wind categories, BDCC terminology, guy wires, structural
inspection, and adult utility actions.

## Archived sources

- The two DTI operations-manual files remain outside the CALM assistant scope;
  the second is an exact byte-for-byte duplicate.
- NDRRMC Memorandum 54, s. 2020 remains a COVID-era administrative source. It
  can be reconsidered only if CALM adds a health-emergency or evacuation-center
  infection-control module.
- The 2009 Fire Code IRR remains a legacy technical reference. Current legal
  or operational checks must use BFP's
  [Revised 2019 RIRR](https://bfp.gov.ph/wp-content/uploads/2019/10/RA9514-RIRR-rev-2019.pdf)
  and local BFP confirmation.

The National Disaster Preparedness Plan still requires reconciliation with
the broader official
[NDRRMP 2020-2030](https://ndrrmc.gov.ph/attachments/article/4147/NDRRMP-Pre-Publication-Copy-v2.pdf),
current agency issuances, and the local DRRMO/school plan before operational
use.

## Transformation rules for Grade 4

| Adult or technical source action | CALM learner transform |
|---|---|
| Shut off LPG or electricity | Do not touch the controls; move away and tell an adult. |
| Use an extinguisher | Alert, evacuate, and stay out; trained adults/responders handle the fire. |
| Inspect a damaged building | Stay away and report what you see to an adult. |
| Establish an evacuation route | The school configures the approved route; the learner follows its marked ID. |
| Conduct headcount | The learner stays with the class and answers roll call; staff use the dashboard. |
| Help a vulnerable person evacuate | Tell the responsible adult and remain with the assigned group; do not perform a physical rescue. |

## New or strengthened holds

1. Quarantine all BFP Volume 1 quiz-answer derivatives until BFP supplies a
   corrected, reviewed answer key.
2. Do not hard-code a school fire-drill frequency: adult BFP sources disagree,
   and current BFP/DepEd/local rules must control.
3. Simulate smoke, blocked exits, alarms, emergency calls, and fire conditions
   virtually. Do not reproduce suggested physical smoke, dry-ice, fumigator,
   or live-fire exercises with Grade 4 participants.
4. The three outdoor-fire cards still require BFP/local DRRMO evidence. Adult
   fire manuals improve the safety boundary but do not provide the missing
   child-specific local route and safe-zone protocol.

## Protocol cleanup completed

- Removed BFP Volume 1 quiz-page 243 from the stair and low-crawl card evidence.
- Removed quiz pages 202 and 304 from the trapped-learner card evidence.
- Reduced the fire assembly/headcount child-manual evidence to verified page
  213 and added the BFP adult evacuation/headcount narrative on pages 418-420
  as an adult-only reference.
- Retained page 202 only inside the explicit fire-suppression conflict card,
  where its disposition is `CONFLICT_REVIEW`, never as approved guidance.
- Added a validator rule that fails the corpus if a quarantined child-manual
  quiz page is used as `KEEP_EXACT`, `SIMPLIFY`, or ordinary learner evidence.

## Runtime consequence

This re-audit broadens the evidence available to CALM without broadening what
the learner can retrieve. Production retrieval remains empty until the atomic
English, Filipino, and Taglish cards complete domain, child-safety, language,
VR-rule, pilot, and UAT approvals.
