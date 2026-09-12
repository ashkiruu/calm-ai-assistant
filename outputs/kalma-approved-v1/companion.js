/* KALMA asset preview. Original body geometry stays fixed; only this SVG overlay changes. */
(() => {
  'use strict';
  const W = 1678, H = 937;
  const descriptions = {
    ready: 'A relaxed gaze, soft cyan light, and an occasional natural blink.',
    blink: 'A short close-and-open blink. Eye centers and spacing remain fixed.',
    listening: 'Centered cyan listening waves pulse gently inside the visor.',
    thinking: 'Three cyan dots brighten in sequence in the center of the visor.',
    speaking: 'A centered cyan waveform moves with the speech rhythm inside the visor.',
    error: 'A steady cyan exclamation mark requests attention inside the visor.',
    happy: 'Two gently smiling cyan eye curves offer quiet encouragement.'
  };
  const face = document.getElementById('face');
  const stage = document.getElementById('stage');
  const pause = document.getElementById('pause');
  const cycle = document.getElementById('cycle');
  const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
  let state = 'ready', started = performance.now(), frozen = false, frozenTime = 0, level = null;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const fmt = v => Number(v.toFixed(3));
  const ease = x => x * x * (3 - 2 * x);
  function blinkAt(t, repeat = 5.4) {
    const phase = t % repeat;
    if (phase < 0.08) return 1 - ease(phase / 0.08) * .94;
    if (phase < .12) return .06;
    if (phase < .25) return .06 + ease((phase - .12) / .13) * .94;
    return 1;
  }
  function markup(current, t) {
    let open = 1, dx = 0, dy = 0, tilt = 0;
    if (current === 'ready') open = blinkAt(t + .8);
    if (current === 'blink') open = blinkAt(t, 2.4);
    const displayOnly = ['listening', 'thinking', 'speaking', 'error'].includes(current);
    const eyes = displayOnly ? '' : [[708, 326, 60, 82, 13], [933, 324, 65, 81, -10]].map(([x,y,rx,ry,angle], i) => {
      const rotation = angle * Math.min(open, 1) + (i ? -tilt : tilt);
      if (open < .13) return `<g transform="translate(${x} ${y})"><path d="M -56 0 Q 0 11 56 0" fill="none" stroke="#99f7fc" stroke-width="9" stroke-linecap="round" filter="url(#eyeBloom)"/></g>`;
      if (current === 'happy') return `<g transform="translate(${x} ${y}) rotate(${angle})"><path d="M -48 10 Q 0 -43 48 10" fill="none" stroke="#99f7fc" stroke-width="23" stroke-linecap="round" filter="url(#eyeBloom)"/></g>`;
      return `<g transform="translate(${x + dx} ${y + dy}) rotate(${rotation})"><ellipse rx="${rx}" ry="${fmt(ry * open)}" fill="url(#eyePaint)" filter="url(#eyeBloom)"/></g>`;
    }).join('');
    let effects = '';
    if (current === 'listening') {
      effects += '<rect x="818" y="321" width="10" height="34" rx="5" fill="#8ce3f0" filter="url(#effectBloom)"/>';
      for (let j = 0; j < 3; j++) {
        const alpha = .24 + .76 * Math.pow((1 + Math.cos(t * Math.PI * 2 / 1.8 - j * .85)) / 2, 2);
        const spread = 29 + j * 39, height = 26 + j * 19;
        effects += `<g fill="none" stroke="#8ce3f0" stroke-width="9" stroke-linecap="round" opacity="${fmt(alpha)}" filter="url(#effectBloom)"><path d="M ${823-spread} ${338-height} Q ${823-spread-22} 338 ${823-spread} ${338+height}"/><path d="M ${823+spread} ${338-height} Q ${823+spread+22} 338 ${823+spread} ${338+height}"/></g>`;
      }
    }
    if (current === 'thinking') {
      for (let i = 0; i < 3; i++) {
        const alpha = .25 + .75 * Math.pow((1 + Math.cos(t * Math.PI * 2 / 2.7 - i * Math.PI * 2 / 3)) / 2, 3);
        effects += `<circle cx="${748+i*75}" cy="338" r="12" fill="#8ce3f0" opacity="${fmt(alpha)}" filter="url(#effectBloom)"/>`;
      }
    }
    if (current === 'speaking') {
      for (let i = 0; i < 9; i++) {
        const envelope = level === null ? (.16 + .84 * Math.pow(Math.sin(t * 5.8 + i * .72), 2)) : level;
        const peak = [20, 40, 70, 100, 128, 100, 70, 40, 20][i];
        const height = 10 + peak * envelope;
        effects += `<rect x="${697+i*30}" y="${fmt(338-height/2)}" width="12" height="${fmt(height)}" rx="6" fill="#8ce3f0" filter="url(#effectBloom)"/>`;
      }
    }
    if (current === 'error') effects += '<g fill="#8ce3f0" filter="url(#effectBloom)"><path d="M 809 265 Q 809 258 816 258 H 830 Q 837 258 837 265 L 833 345 Q 833 352 826 352 H 820 Q 813 352 813 345 Z"/><circle cx="823" cy="389" r="14"/></g>';
    return `<defs><radialGradient id="eyePaint" cx="40%" cy="35%"><stop stop-color="#a8fcfc"/><stop offset="1" stop-color="#83eff5"/></radialGradient><filter id="eyeBloom" x="-65%" y="-65%" width="230%" height="230%"><feGaussianBlur stdDeviation="10" result="blur"/><feComponentTransfer in="blur" result="dim"><feFuncA type="linear" slope=".48"/></feComponentTransfer><feMerge><feMergeNode in="dim"/><feMergeNode in="SourceGraphic"/></feMerge></filter><filter id="effectBloom" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>${eyes}${effects}`;
  }
  function render(t) { face.innerHTML = markup(state, t); }
  function setState(next) {
    if (!(next in descriptions)) throw new Error(`Unknown KALMA state: ${next}`);
    state = next; started = performance.now(); frozenTime = next === 'blink' ? .04 : .6;
    document.querySelectorAll('[data-state]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.state === state)));
    document.getElementById('description').textContent = descriptions[state];
    stage.setAttribute('aria-label', `KALMA: ${state === 'error' ? 'needs attention' : state}`);
    render(frozenTime);
  }
  function frame(now) {
    if (!frozen) {
      const elapsed = (now - started) / 1000;
      if (cycle.checked && elapsed > 5.4) {
        const states = Object.keys(descriptions);
        setState(states[(states.indexOf(state) + 1) % states.length]);
      } else render(elapsed);
    }
    requestAnimationFrame(frame);
  }
  document.querySelectorAll('[data-state]').forEach(button => button.addEventListener('click', () => setState(button.dataset.state)));
  pause.addEventListener('change', () => {
    frozen = pause.checked;
    if (frozen) frozenTime = (performance.now() - started) / 1000;
    else started = performance.now() - frozenTime * 1000;
  });
  function applyPreference() { frozen = motionPreference.matches; pause.checked = frozen; if (frozen) render(.6); }
  motionPreference.addEventListener('change', applyPreference);
  window.kalmaPreview = {
    setState,
    seek(seconds) { frozen = true; pause.checked = true; frozenTime = seconds; render(seconds); },
    play() { frozen = false; pause.checked = false; started = performance.now() - frozenTime * 1000; },
    setLevel(value) { level = value === null ? null : clamp(Number.isFinite(value) ? value : 0, 0, 1); },
    overlaySvg(current = state, seconds = .6) { return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${markup(current, seconds)}</svg>`; },
    dimensions: { width: W, height: H },
    states: Object.keys(descriptions)
  };
  if (new URLSearchParams(location.search).has('export')) document.body.classList.add('export');
  setState('ready'); applyPreference(); requestAnimationFrame(frame);
})();
