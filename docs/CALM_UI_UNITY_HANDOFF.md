# CALM UI Unity Handoff

## Purpose

`/simulation` is a behavioral and visual previsualization of the learner-facing
CALM interface. It is not a WebXR client, a replacement for Unity physics, or a
VR-comfort validation build. Its job is to make the UI state machine, cue
priority, subtitles, voice flow, and mission-response mapping reviewable. The
corresponding KALMA components are now installed in the eight Unity mission
scenes; the browser remains the fast review surface.

The existing Mission Control page remains the engineering oracle. Both pages
load `school-earthquake-minimal` and use the same trusted state envelope.

## Web-to-Unity component map

| Web prototype responsibility | Unity component | Required input |
|---|---|---|
| Cyan/green companion halo and waveform | `AIAssistantHUD` | `KalmaVisualState` |
| Learner and assistant dialogue lines | `MissionHUD` | transcript/question and `response_text` |
| Desk, window, cabinet, exit, and zone outlines | `SpatialCuePresenter` | state ID plus local scene object registry |
| Ground arrows | `RouteMarkerPresenter` | current route snapshot and `selected_route_id` |
| Push-to-talk lifecycle | `CalmPushToTalk` | microphone input and current trusted task ID |
| Earcons, spatial voice, and ducking | `CalmAssistant` | visual state, TTS clip, active scene audio |
| Preview state selector | Development-only `MissionStateDebugPanel` | mission contract; exclude from learner build |

## KALMA placement and interaction

KALMA is the visible persona of the CALM assistant. The persona communicates
system state, but it is not the primary interaction target: a learner should
never need to aim a ray at KALMA during a hazard.

The current verified placement is a head-relative lower-right peripheral anchor
at viewport `(0.86, 0.22)` and about `0.85 m` from the camera. It remains visible
beside the briefing board and drill HUD without covering the learner's central
hazard or route view. KALMA is an indicator, not a ray target; the learner never
needs to aim at it during a hazard.

A non-dominant wrist dock remains a future hardware-comfort option. Do not add
it until it has been checked on the target Quest headset for hand dominance,
seated/standing height, controller occlusion, and motion comfort.

`CalmPushToTalk` uses a Unity Input System action named `CALM_PushToTalk`:

- default binding: left-controller secondary button (`Y` on Meta controllers);
- mirrored binding: right-controller secondary button (`B`) for left-handed mode;
- editor fallback: `V`; browser preview uses its on-screen/keyboard control;
- interaction: hold to record, release to submit—never toggle recording.

The hold begins only after the start-listening earcon. Releasing captures an
immutable trusted context snapshot, stops recording, and enters `Thinking`.
Local locomotion guards remain active throughout.

## Comms state machine

```csharp
public enum CalmCommsState
{
    Ready,
    Listening,
    Thinking,
    Speaking,
    Error
}
```

The state transition order is:

```text
Ready -> Listening -> Thinking -> Speaking -> Ready
                         |             |
                         +-- Error <---+
```

- `Listening`: cyan halo and signal arcs, animated waveform, start-listening earcon.
- `Thinking`: orange status; keep the learner transcript visible.
- `Speaking`: green aura around KALMA, response subtitle, response-start earcon, hazard
  audio ducked beneath the assistant voice.
- `Error`: coral status and readable text fallback. Never remove the last safe
  instruction because audio failed.

## Trusted-state and response mapping

Unity owns the current state and all scene geometry. Learner speech remains a
question and cannot select routes, hazards, cover, alarm meaning, or mission
state.

1. Unity captures an immutable `ContextSnapshot` when push-to-talk ends.
2. Send the learner audio and that complete snapshot to the CALM voice boundary.
3. Discard a response if its session, scenario, revision, state ID, or sequence
   no longer matches the captured snapshot.
4. Display `response_text` immediately.
5. Play `tts_text` exactly for P0/P1 guidance.
6. Enable route markers only when `movement_authorized` is true and
   `selected_route_id` exists in the captured route snapshot.
7. Render prohibited cues from local colliders and `blocked_action_codes`; do
   not wait for a network round trip before stopping an unsafe movement.

## Scene object registry

The browser uses descriptive demo IDs. Unity should bind equivalent IDs to
actual scene objects through a serialized registry rather than searching by
display name.

| Demo cue | Unity binding |
|---|---|
| `desk-center` | nearest configured sturdy-cover collider |
| `windows` | all classroom glass hazard colliders |
| `cabinet` | configured falling-object hazard |
| `exit` | classroom exit/route gate |
| `assembly` | configured assembly-zone volume |
| `assembly-cover` | locally approved aftershock protection point |
| `teacher` | fictional teacher guide anchor |

Outlines are local visual feedback. The backend returns safety decisions but
does not invent which mesh should glow.

## Spatial UI placement

- Keep the subtitle panel head-locked but below the center of view, roughly in
  the lower 20–25 percent of the comfortable field.
- Keep the companion indicator offset from the central hazard view.
- Use world-space route arrows close to the floor.
- Avoid large full-screen flashes, rapid camera motion, or animated UI attached
  to the learner's head during shaking.
- Provide a reduced-motion option that removes camera shake while retaining
  hazard audio and all instructional cues.

## Audio mixer layout

```text
Master
├── AssistantVoice   (priority, spatial anchor near companion)
├── Earcons          (short, non-startling)
├── HazardAmbient    (ducked while AssistantVoice plays)
├── Alarm            (ducked for P0/P1 guidance)
└── Environment
```

Use an exposed mixer snapshot for voice guidance rather than changing every
source individually. A P0 response may interrupt lower-priority assistant
speech. Ducking should begin quickly and recover gradually after the guidance
clip ends.

## Prototype-only behavior

- WASD, mouse-look, touch arrows, and the Canvas renderer are browser preview
  controls; Unity locomotion and collision remain authoritative.
- The state dropdown is a development tool for reviewing all 16 callable
  contract states independently.
- Browser stereo placement approximates companion direction. Unity should use
  the project's spatial audio system and tested headset settings.
- Route, alarm, assembly, and school identifiers are synthetic until the
  partner school's signed configuration replaces them.

## Unity acceptance checks

- Every callable mission state produces the same subtitle, protocol, action,
  route, zone, movement authorization, and blocked actions as Mission Control.
- Unsafe local movement is blocked before the response arrives.
- A stale response never changes a route or visual cue.
- P0 speech interrupts lower-priority speech and ducks hazard audio.
- Text remains readable when TTS, microphone, or network synthesis is absent.
- No learner recording, transcript, name, or device identifier is persisted or
  forwarded to the dashboard event.
- Comfort checks cover seated/standing height, subtitle placement, peripheral
  visibility, reduced motion, and the target Meta headset refresh rate.
