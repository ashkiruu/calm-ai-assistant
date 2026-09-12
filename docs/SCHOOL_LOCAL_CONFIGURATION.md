# School alarms, routes, assembly, and reunification

These four items make a general disaster protocol usable in a particular school.
They are not facts that CALM should guess from a manual or generate with an LLM.

## What each item is for

### Alarm or cue

The alarm tells the learner what recognized school event has started. The school
must define the cue ID, exact meaning, applicable hazard and phase, and reviewed
learner instruction. For earthquakes, active shaking always overrides an
evacuation cue: protect first, then evacuate only after trusted state says shaking
has stopped and the teacher-led evacuation state is active.

An alarm by itself must never mean that a building is safe to re-enter or that a
child may be released.

### Route

A route is the school-approved path from a known zone to an approved destination.
CALM needs opaque IDs, origin, destination, explicitly approved alternate, and a
fresh trusted runtime status (`OPEN`, `BLOCKED`, `CLOSED`, or `UNKNOWN`). If the
primary route is unavailable, CALM may use only the configured open alternate.
If none exists, it tells the learner to stay with the teacher; it never invents a
hallway, staircase, gate, or shortcut.

### Assembly area

The assembly area is where the class stays immediately after evacuation so staff
can protect the group and account for learners. CALM may tell a child to stay with
the class, answer headcount, report an injury or a missing classmate, and wait.
It must never send the learner back to search or perform rescue.

### Reunification

Reunification happens later. It is the controlled school process for releasing a
learner to an authorized adult after staff verification. Assembly is for immediate
safety and accountability; reunification is for controlled release.

CALM does not verify identity and does not decide who may collect a child. It may
receive only a minimal authenticated status such as `NOT_AUTHORIZED` or
`AUTHORIZED`, plus confirmation that designated staff are present. Names,
contacts, custody notes, photos, IDs, signatures, and authorization tokens stay in
the school's separate process and are not stored or embedded by CALM.

## Who must provide and confirm the data

Ask the partner school's:

- school head or authorized administrator;
- School DRRM coordinator;
- facilities/safety representative who maintains the campus evacuation map;
- designated learner-release/reunification lead; and
- relevant division/local DRRM or hazard authority reviewer when required.

Request the current signed school DRRM/contingency plan, evacuation map revision,
drill alarm meanings, primary and alternate routes per VR zone, assembly-area
assignments, headcount procedure, re-entry authority, and reunification workflow.
Do not derive operational paths solely from a national PDF.

## Before partner-school data arrives

The repository uses [school_profile.demo.json](../config/school_profile.demo.json).
Its values are synthetic and clearly marked:

- status: `DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED`;
- real-emergency use: `false`;
- simulation cues: `SIM_*`;
- placeholder routes: `ROUTE_CLASSROOM_A_*`; and
- placeholder assembly area: `ASSEMBLY_A`.

They are sufficient for software and VR integration tests, but must not be shown
as the real school's procedure.

## Activation checklist for a real partner-school profile

1. Replace every placeholder with opaque IDs tied to the approved Unity map.
2. Separate static approved topology from live route/assembly state.
3. Record the profile revision, campus-map revision, effective date, and hash.
4. Obtain the required reviewers' decisions on the same revision and hash.
5. Test primary blocked, alternate open, all routes unavailable, assembly closed,
   aftershock, missing learner, and unauthorized release states.
6. Verify EN/FIL/Taglish meaning equivalence and Grade 4 readability.
7. Confirm local configuration and identity/release data never appear in RAG,
   prompts, transcripts, or learner-facing logs.
8. Activate only after the school approves the profile and the relevant protocol
   cards reach `RUNTIME_APPROVED`.
