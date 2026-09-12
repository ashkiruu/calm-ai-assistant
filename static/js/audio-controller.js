export class CalmAudioController {
    constructor() {
        this.context = null;
        this.master = null;
        this.ambientGain = null;
        this.voiceGain = null;
        this.ambientOscillators = [];
        this.enabled = true;
        this.shaking = false;
        this.activeVoice = null;
    }

    ensureContext() {
        if (!this.context) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) throw new Error("Web Audio is unavailable in this browser.");
            this.context = new AudioContext();
            this.master = this.context.createGain();
            this.master.gain.value = this.enabled ? 0.9 : 0;
            this.master.connect(this.context.destination);

            this.ambientGain = this.context.createGain();
            this.ambientGain.gain.value = 0;
            this.ambientGain.connect(this.master);

            this.voiceGain = this.context.createGain();
            this.voiceGain.gain.value = 1;
            this.voiceGain.connect(this.master);
            this.createAmbientRumble();
            this.ambientGain.gain.value = this.shaking ? 0.11 : 0;
        }
        if (this.context.state === "suspended") this.context.resume();
        return this.context;
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (!this.context) return;
        const now = this.context.currentTime;
        this.master.gain.cancelScheduledValues(now);
        this.master.gain.setTargetAtTime(enabled ? 0.9 : 0, now, 0.04);
    }

    createAmbientRumble() {
        const filter = this.context.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.value = 95;
        filter.Q.value = 0.8;
        filter.connect(this.ambientGain);

        for (const [frequency, amount] of [[34, 0.55], [51, 0.32], [67, 0.16]]) {
            const oscillator = this.context.createOscillator();
            const gain = this.context.createGain();
            oscillator.type = frequency === 34 ? "sine" : "triangle";
            oscillator.frequency.value = frequency;
            gain.gain.value = amount;
            oscillator.connect(gain).connect(filter);
            oscillator.start();
            this.ambientOscillators.push(oscillator);
        }
    }

    setShaking(active) {
        this.shaking = active;
        if (!this.context) return;
        const now = this.context.currentTime;
        const target = active && this.enabled ? 0.11 : 0;
        this.ambientGain.gain.cancelScheduledValues(now);
        this.ambientGain.gain.setTargetAtTime(target, now, active ? 0.2 : 0.35);
    }

    async earcon(kind) {
        if (!this.enabled) return;
        const context = this.ensureContext();
        const now = context.currentTime;
        const tones = kind === "listen" ? [660, 880] : kind === "respond" ? [523, 659, 784] : [330, 262];
        tones.forEach((frequency, index) => {
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            oscillator.type = "sine";
            oscillator.frequency.value = frequency;
            const start = now + index * 0.075;
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(0.075, start + 0.018);
            gain.gain.exponentialRampToValueAtTime(0.001, start + 0.13);
            oscillator.connect(gain).connect(this.master);
            oscillator.start(start);
            oscillator.stop(start + 0.15);
        });
    }

    duckAmbient(ducked) {
        if (!this.context) return;
        const now = this.context.currentTime;
        const normal = this.shaking ? 0.11 : 0;
        const target = ducked ? normal * 0.22 : normal;
        this.ambientGain.gain.cancelScheduledValues(now);
        this.ambientGain.gain.setTargetAtTime(target, now, ducked ? 0.045 : 0.28);
    }

    stopVoice() {
        if (!this.activeVoice) return;
        try { this.activeVoice.stop(); } catch { /* Already stopped. */ }
        this.activeVoice = null;
        this.duckAmbient(false);
    }

    async playVoice(blob, { onStart, onEnd } = {}) {
        if (!this.enabled) {
            onEnd?.();
            return;
        }
        const context = this.ensureContext();
        this.stopVoice();
        const buffer = await context.decodeAudioData(await blob.arrayBuffer());
        const source = context.createBufferSource();
        source.buffer = buffer;

        let destination = this.voiceGain;
        if (typeof context.createStereoPanner === "function") {
            const panner = context.createStereoPanner();
            panner.pan.value = -0.22;
            panner.connect(this.voiceGain);
            destination = panner;
        }
        source.connect(destination);
        this.activeVoice = source;
        this.duckAmbient(true);
        onStart?.();
        return new Promise(resolve => {
            source.onended = () => {
                if (this.activeVoice === source) this.activeVoice = null;
                this.duckAmbient(false);
                onEnd?.();
                resolve();
            };
            source.start();
        });
    }
}
