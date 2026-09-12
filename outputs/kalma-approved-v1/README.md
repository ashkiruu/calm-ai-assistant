# KALMA approved robot — expression assets

Open `index.html` for the animated preview. Everything runs locally, without dependencies or network access.

This is a review package, not a replacement for the current simulation component.
The supplied robot image was edited with the built-in image-generation tool to remove its eyes.
The generated base closely follows the approved reference but is not guaranteed pixel-identical to it.
Every expression in this package uses exactly the same base image, angle, position, size and lighting.
The gray studio background is retained; the robot PNG is not transparent.

## Included states

- Ready: normal cyan oval eyes and occasional blink.
- Blink: half-closed and fully closed frames, with close/open motion in the preview.
- Listening: centered cyan listening arcs pulse inside the visor, replacing the eyes.
- Thinking: three centered cyan dots brighten in sequence, replacing the eyes.
- Speaking: a nine-bar cyan waveform animates in the visor center, replacing the eyes.
- Needs attention: a steady cyan exclamation mark replaces the eyes.
- Encouragement: two smiling cyan curves.

`frames/` contains full-size, consistently aligned PNG keyframes.
`overlays/` contains transparent SVG eye/effect layers, aligned to `robot-base.png` at 1678 × 937.
`manifest.json` records all frame states and sampling times.
The approved photograph remains a reference; all deliverable states use the one generated base.

## Playback

The preview keeps the body fixed. Listening repeats every 1.8 seconds; thinking every 2.7 seconds.
Blink closes in 80 ms, holds for 40 ms, and opens over 130 ms.
Normal idle blinks roughly every 5.4 seconds.
Speaking uses a demonstration rhythm. For real playback, feed normalized voice amplitude to
`window.kalmaPreview.setLevel(0..1)`; pass `null` to return to the demo rhythm.
Use `setState('ready'|'blink'|'listening'|'thinking'|'speaking'|'error'|'happy')` to change expression.
`seek(seconds)` freezes a deterministic frame. `play()` resumes.
Reduced motion is respected automatically; each state retains a distinct static expression.

## Generation prompt

Precise edit of the approved KALMA photograph. Remove only the two glowing cyan eye graphics
and their cyan bloom, restoring the glossy black visor with subtle reflections. Preserve
the ivory shell, silhouette, integrated arms, seams, camera angle, proportions, lighting,
gray studio background, floor shadow and landscape composition. No redesign, additional
features, mouth, text or accessories. Output one blank-visor base image for animated overlays.

The initial transparency attempt was discarded because it contained a painted checkerboard.
No simulated transparency is included in this package. A production cutout or 3D model is a
separate next step after visual approval.
