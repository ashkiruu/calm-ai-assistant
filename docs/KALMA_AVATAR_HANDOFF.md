# KALMA animated avatar

KALMA is implemented as a dependency-free Web Component in
`static/js/kalma-avatar.js`. The artwork is inline SVG, so it remains sharp at
any size and each eye, light, shell layer, and glow can animate independently.

## Use

Import the component once:

```js
import "/static/js/kalma-avatar.js";
```

Place it inside any sized container:

```html
<kalma-avatar id="kalma" state="ready"></kalma-avatar>
```

Change its state with either API:

```js
const kalma = document.querySelector("kalma-avatar");
kalma.setState("speaking");
kalma.setAttribute("state", "listening");
```

Supported states are `ready`, `listening`, `thinking`, `speaking`, and `error`.

## Visual design and behavior

KALMA is a compact ivory robot with a glossy black visor and face-only visual
states. The production component uses the approved generated robot cutout at
static/assets/kalma/robot-base.png; a transparent SVG layer is aligned to the
same 1678 × 937 image coordinates so the body, camera angle, and scale remain
fixed.

- Ready shows two cyan oval eyes with a natural blink.
- Listening replaces the eyes with centered cyan listening waves inside the visor.
- Thinking replaces the eyes with three cyan dots that brighten in sequence.
- Speaking replaces the eyes with a centered nine-bar cyan waveform.
- Error replaces the eyes with a steady cyan exclamation mark.
- `prefers-reduced-motion` automatically disables ambient and state animation
  while preserving each state's identifying posture and color.

## Theme tokens

Override these CSS custom properties on the component:

```css
kalma-avatar {
    --kalma-ivory: #e8e0c8;
    --kalma-sage: #8fa58b;
    --kalma-face: #183b3e;
    --kalma-eye: #8ce3dd;
    --kalma-amber: #e7b86d;
    --kalma-coral: #d98778;
}
```

The state overlay is intentionally simple so it reads at VR scale. The
surrounding simulation status card remains available as text for clarity, while
the robot itself communicates only through its visor.

## Integration note

`simulation.html` already uses the component. `static/js/simulation.js` sends
the application state to the avatar whenever KALMA starts listening, checks
guidance, speaks, becomes ready, or reports an error.
