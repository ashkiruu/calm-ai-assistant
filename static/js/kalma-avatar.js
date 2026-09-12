const template = document.createElement("template");
template.innerHTML = [
    "<style>",
    ":host{display:block;width:100%;height:100%;contain:layout paint style}",
    ".stage{position:relative;width:100%;height:100%;overflow:visible}",
    ".base,.overlay{position:absolute;inset:0;display:block;width:100%;height:100%;pointer-events:none}",
    ".base{object-fit:cover;object-position:center}",
    ".overlay{overflow:visible}",
    ".state{display:none}",
    ".ready-state{display:block}",
    ".eye{transform-box:fill-box;transform-origin:center;filter:url(#eyeGlow);animation:blink 6.2s ease-in-out infinite}",
    ".eye-right{animation-delay:70ms}",
    ".listen-wave,.thinking-dot,.voice-bar{transform-box:fill-box;transform-origin:center}",
    ".listen-wave{opacity:0;animation:listenRipple 1.8s ease-out infinite}",
    ".listen-wave:nth-child(3){animation-delay:.62s}",
    ".listen-wave:nth-child(4){animation-delay:1.24s}",
    ".thinking-dot{opacity:.25;animation:thinkDot 2.7s ease-in-out infinite}",
    ".thinking-dot:nth-child(2){animation-delay:-.9s}",
    ".thinking-dot:nth-child(3){animation-delay:-1.8s}",
    ".voice-bar{animation:speakBar .56s ease-in-out infinite alternate;transform-origin:center}",
    ".voice-bar:nth-child(2){animation-delay:-.12s}.voice-bar:nth-child(3){animation-delay:-.24s}.voice-bar:nth-child(4){animation-delay:-.34s}.voice-bar:nth-child(5){animation-delay:-.44s}",
    ":host([state=listening]) .state-listening,:host([state=thinking]) .state-thinking,:host([state=speaking]) .state-speaking,:host([state=error]) .state-error{display:block}",
    ":host([state=listening]) .ready-state,:host([state=thinking]) .ready-state,:host([state=speaking]) .ready-state,:host([state=error]) .ready-state{display:none}",
    ":host([reduced-motion]) *,.reduced-motion *{animation:none!important}",
    "@media (prefers-reduced-motion:reduce){.overlay *{animation:none!important}}",
    "@keyframes blink{0%,44%,48%,78%,82%,100%{transform:scaleY(1)}46%,80%{transform:scaleY(.08)}}",
    "@keyframes listenRipple{0%{opacity:.08;transform:scale(.7)}20%{opacity:.95}100%{opacity:0;transform:scale(1.22)}}",
    "@keyframes thinkDot{0%,100%{opacity:.25;transform:scale(.75)}45%{opacity:1;transform:scale(1.18)}}",
    "@keyframes speakBar{from{transform:scaleY(.35);opacity:.72}to{transform:scaleY(1.35);opacity:1}}",
    "</style>",
    '<div class="stage"><img class="base" src="/static/assets/kalma/robot-base.png" alt="" draggable="false">',
    '<svg class="overlay" viewBox="0 0 1678 937" preserveAspectRatio="xMidYMid slice" aria-hidden="true">',
    '<defs><radialGradient id="eyePaint" cx="40%" cy="35%"><stop stop-color="#A8FCFC"/><stop offset="1" stop-color="#83EFF5"/></radialGradient>',
    '<filter id="eyeGlow" x="-65%" y="-65%" width="230%" height="230%"><feGaussianBlur stdDeviation="10" result="blur"/><feComponentTransfer in="blur" result="dim"><feFuncA type="linear" slope=".48"/></feComponentTransfer><feMerge><feMergeNode in="dim"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
    '<filter id="effectGlow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
    '<g class="state ready-state" fill="url(#eyePaint)"><ellipse class="eye eye-left" cx="708" cy="326" rx="60" ry="82"/><ellipse class="eye eye-right" cx="933" cy="324" rx="65" ry="81"/></g>',
    '<g class="state state-listening" fill="none" stroke="#8CE3F0" stroke-width="9" stroke-linecap="round" filter="url(#effectGlow)"><path class="listen-wave" d="M794 312Q760 338 794 364"/><path class="listen-wave" d="M852 288Q786 338 852 388"/><path class="listen-wave" d="M910 266Q808 338 910 410"/></g>',
    '<g class="state state-thinking" fill="#8CE3F0" filter="url(#effectGlow)"><circle class="thinking-dot" cx="748" cy="338" r="12"/><circle class="thinking-dot" cx="823" cy="338" r="12"/><circle class="thinking-dot" cx="898" cy="338" r="12"/></g>',
    '<g class="state state-speaking" fill="#8CE3F0" filter="url(#effectGlow)"><rect class="voice-bar" x="697" y="328" width="12" height="20" rx="6"/><rect class="voice-bar" x="727" y="318" width="12" height="40" rx="6"/><rect class="voice-bar" x="757" y="303" width="12" height="70" rx="6"/><rect class="voice-bar" x="787" y="288" width="12" height="100" rx="6"/><rect class="voice-bar" x="817" y="275" width="12" height="126" rx="6"/><rect class="voice-bar" x="847" y="288" width="12" height="100" rx="6"/><rect class="voice-bar" x="877" y="303" width="12" height="70" rx="6"/><rect class="voice-bar" x="907" y="318" width="12" height="40" rx="6"/><rect class="voice-bar" x="937" y="328" width="12" height="20" rx="6"/></g>',
    '<g class="state state-error" fill="#8CE3F0" filter="url(#effectGlow)"><path d="M809 265Q809 258 816 258H830Q837 258 837 265L833 345Q833 352 826 352H820Q813 352 813 345Z"/><circle cx="823" cy="389" r="14"/></g>',
    '</svg></div>'
].join("");

const stateLabels = {
    ready: "KALMA is ready.",
    listening: "KALMA is listening.",
    thinking: "KALMA is checking guidance.",
    speaking: "KALMA is speaking.",
    error: "KALMA needs attention."
};

export class KalmaAvatar extends HTMLElement {
    static observedAttributes = ["state"];

    constructor() {
        super();
        this.attachShadow({ mode: "open" }).append(template.content.cloneNode(true));
        this.state = this.getAttribute("state") || "ready";
        this.reducedMotion = false;
    }

    connectedCallback() {
        if (!this.hasAttribute("state")) this.setAttribute("state", "ready");
        this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (this.reducedMotion) this.setAttribute("reduced-motion", "");
        this.setAttribute("aria-label", stateLabels[this.state] || stateLabels.ready);
    }

    disconnectedCallback() {}

    attributeChangedCallback(name, oldValue, newValue) {
        if (name !== "state" || oldValue === newValue) return;
        this.state = stateLabels[newValue] ? newValue : "ready";
        this.setAttribute("aria-label", stateLabels[this.state]);
    }

    setState(state) {
        this.setAttribute("state", state);
    }
}

if (!customElements.get("kalma-avatar")) customElements.define("kalma-avatar", KalmaAvatar);
