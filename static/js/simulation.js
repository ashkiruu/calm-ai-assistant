import { CalmClient } from "./calm-client.js?v=20260829-conversation";
import { CalmAudioController } from "./audio-controller.js";
import { LowPolyScene } from "./simulation-scene.js";
import "./kalma-avatar.js";

const elements = {
    shell: document.getElementById("simulationShell"),
    canvas: document.getElementById("sceneCanvas"),
    apiDot: document.getElementById("apiDot"),
    apiStatus: document.getElementById("apiStatus"),
    phase: document.getElementById("phaseLabel"),
    scene: document.getElementById("sceneLabel"),
    comms: document.getElementById("commsWidget"),
    kalmaAvatar: document.getElementById("kalmaAvatar"),
    commsState: document.getElementById("commsState"),
    objective: document.getElementById("objectiveLabel"),
    objectiveHint: document.getElementById("objectiveHint"),
    alert: document.getElementById("proximityAlert"),
    alertKind: document.getElementById("alertKind"),
    alertText: document.getElementById("alertText"),
    learnerLine: document.getElementById("learnerLine"),
    learnerSubtitle: document.getElementById("learnerSubtitle"),
    calmSubtitle: document.getElementById("calmSubtitle"),
    protocol: document.getElementById("protocolLabel"),
    movement: document.getElementById("movementLabel"),
    ptt: document.getElementById("pttButton"),
    panelToggle: document.getElementById("panelToggle"),
    panel: document.getElementById("previewPanel"),
    closePanel: document.getElementById("closePanel"),
    stateSelect: document.getElementById("stateSelect"),
    stateCode: document.getElementById("stateCode"),
    routeCode: document.getElementById("routeCode"),
    locale: document.getElementById("localeSelect"),
    question: document.getElementById("questionInput"),
    ask: document.getElementById("askButton"),
    audioToggle: document.getElementById("audioToggle"),
    motionToggle: document.getElementById("motionToggle"),
    toast: document.getElementById("toast")
};

const client = new CalmClient();
const audio = new CalmAudioController();
const scene = new LowPolyScene(elements.canvas, { onAlert: renderAlert });

let busy = false;
let mediaRecorder = null;
let mediaStream = null;
let audioChunks = [];
let recordingStartedAt = 0;
let talkHeld = false;
let toastTimer = null;
let requestSequence = 0;

const companionLabels = {
    ready: "Ready",
    listening: "Listening",
    thinking: "Checking guidance",
    speaking: "Speaking",
    error: "Needs attention"
};

function setCompanionState(state) {
    elements.comms.dataset.state = state;
    elements.kalmaAvatar?.setState(state);
    elements.commsState.textContent = companionLabels[state] ?? state;
    elements.comms.setAttribute("aria-label", `KALMA assistant status: ${companionLabels[state] ?? state}`);
}

function showToast(message, error = false) {
    clearTimeout(toastTimer);
    elements.toast.textContent = message;
    elements.toast.classList.toggle("error", error);
    elements.toast.classList.add("show");
    toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 3400);
}

function renderAlert(alert) {
    if (!alert) {
        elements.alert.classList.remove("show", "caution");
        return;
    }
    elements.alert.classList.toggle("caution", alert.kind === "caution");
    elements.alertKind.textContent = alert.kind === "caution" ? "Caution" : "Prohibited area";
    elements.alertText.textContent = alert.text;
    elements.alert.classList.add("show");
}

function setPanel(open) {
    elements.panel.classList.toggle("open", open);
    elements.panel.setAttribute("aria-hidden", String(!open));
    elements.panelToggle.setAttribute("aria-expanded", String(open));
    if (open) elements.stateSelect.focus();
    else elements.canvas.focus({ preventScroll: true });
}

function populateStates(scenarios) {
    elements.stateSelect.replaceChildren(...scenarios.map(scenario => {
        const option = document.createElement("option");
        option.value = scenario.id;
        option.textContent = `${scenario.id} · ${scenario.label}`;
        return option;
    }));
    elements.stateSelect.disabled = false;
    elements.ask.disabled = false;
    elements.ptt.disabled = false;
}

function selectState(stateId) {
    if (busy) {
        showToast("Finish the current CALM response before changing state.", true);
        elements.stateSelect.value = client.selected?.id ?? stateId;
        return;
    }
    const scenario = client.selectState(stateId);
    const visual = scene.setState(stateId);
    elements.phase.textContent = visual.phase;
    elements.scene.textContent = visual.scene;
    elements.objective.textContent = scenario.label;
    elements.objectiveHint.textContent = visual.hint;
    elements.stateCode.textContent = scenario.id;
    elements.routeCode.textContent = scenario.expectedRoute ?? (visual.route === "preview" ? "Preview only" : "Locked");
    elements.protocol.textContent = scenario.protocolId;
    elements.movement.textContent = scenario.expectedMovement ? "Route preview expected" : "Movement not authorized";
    elements.learnerLine.hidden = true;
    elements.calmSubtitle.textContent = "Ask KALMA what to do in this trusted state.";
    scene.setResponse(null);
    audio.setShaking(Boolean(visual.shaking));
    setCompanionState("ready");
}

function setBusy(next) {
    busy = next;
    elements.ask.disabled = next || !client.selected;
    elements.ptt.disabled = next || !client.selected;
    elements.stateSelect.disabled = next || !client.scenarios.length;
}

function renderQuestion(text) {
    const clean = text?.trim();
    elements.learnerLine.hidden = !clean;
    elements.learnerSubtitle.textContent = clean || "";
}

function renderResponse(result) {
    const scenario = client.selected;
    const evidenceId = result.retrieved_evidence_ids?.[0] ?? scenario?.protocolId ?? "Grounded";
    const answerMode = result.answer_source === "llm" ? "Conversational" : "Trusted fallback";
    const movementAuthorized = scenario?.expectedMovement === true;
    const selectedRoute = movementAuthorized ? scenario.expectedRoute : null;
    elements.calmSubtitle.textContent = result.response_text || "CALM returned no learner-facing text.";
    elements.protocol.textContent = `${evidenceId} · ${answerMode}`;
    elements.movement.textContent = movementAuthorized
        ? `Movement authorized · ${selectedRoute}`
        : "Movement not authorized";
    elements.routeCode.textContent = selectedRoute ?? "Locked";
    scene.setResponse({
        movement_authorized: movementAuthorized,
        selected_route_id: selectedRoute,
        context_status: "valid"
    });
}

function fallbackSpeech(text) {
    return new Promise(resolve => {
        if (!("speechSynthesis" in window) || !elements.audioToggle.checked) {
            resolve();
            return;
        }
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = client.locale === "fil-PH" ? "fil-PH" : "en-PH";
        utterance.rate = 0.94;
        utterance.onstart = () => {
            setCompanionState("speaking");
            audio.duckAmbient(true);
        };
        utterance.onend = () => {
            audio.duckAmbient(false);
            setCompanionState("ready");
            resolve();
        };
        utterance.onerror = () => {
            audio.duckAmbient(false);
            setCompanionState("ready");
            resolve();
        };
        speechSynthesis.speak(utterance);
    });
}

async function speakResponse(text) {
    if (!text || !elements.audioToggle.checked) {
        setCompanionState("ready");
        return;
    }
    await audio.earcon("respond");
    try {
        const blob = await client.speak(text);
        await audio.playVoice(blob, {
            onStart: () => setCompanionState("speaking"),
            onEnd: () => setCompanionState("ready")
        });
    } catch (error) {
        showToast("Network voice unavailable; using the browser voice.");
        await fallbackSpeech(text);
    }
}

async function completeQuestion(promise, stateSnapshot, sequence) {
    try {
        const result = await promise;
        if (sequence !== requestSequence || client.selected?.id !== stateSnapshot) return;
        if (result.state_id && result.state_id !== stateSnapshot) {
            throw new Error("A stale response was ignored because the mission state changed.");
        }
        renderQuestion(result.transcript ?? result.transcription ?? result.question ?? elements.question.value);
        renderResponse(result);
        await speakResponse(result.tts_text || result.response_text);
    } catch (error) {
        if (sequence !== requestSequence) return;
        setCompanionState("error");
        elements.calmSubtitle.textContent = error.message;
        showToast(error.message, true);
        await audio.earcon("error").catch(() => {});
    } finally {
        if (sequence === requestSequence) setBusy(false);
    }
}

async function askTyped() {
    const question = elements.question.value.trim();
    if (!question || busy || !client.selected) return;
    renderQuestion(question);
    setBusy(true);
    setCompanionState("thinking");
    elements.calmSubtitle.textContent = "Checking the trusted state…";
    const stateSnapshot = client.selected.id;
    const sequence = ++requestSequence;
    await completeQuestion(client.ask(question), stateSnapshot, sequence);
}

function preferredRecordingType() {
    const options = [
        "audio/webm;codecs=opus",
        "audio/ogg;codecs=opus",
        "audio/mp4",
        "audio/webm"
    ];
    return options.find(type => MediaRecorder.isTypeSupported(type)) ?? "";
}

async function startRecording() {
    if (busy || mediaRecorder || !client.selected) return;
    if (!navigator.mediaDevices?.getUserMedia || !("MediaRecorder" in window)) {
        setPanel(true);
        showToast("Microphone recording is unavailable. Use the typed fallback.", true);
        return;
    }
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 }
        });
        if (!talkHeld) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
            setCompanionState("ready");
            return;
        }
        const mimeType = preferredRecordingType();
        mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream);
        audioChunks = [];
        mediaRecorder.ondataavailable = event => {
            if (event.data.size) audioChunks.push(event.data);
        };
        mediaRecorder.onstop = submitRecording;
        mediaRecorder.start(160);
        recordingStartedAt = performance.now();
        elements.ptt.classList.add("recording");
        elements.ptt.querySelector("strong").textContent = "Listening…";
        setCompanionState("listening");
        elements.calmSubtitle.textContent = "I’m listening.";
        await audio.earcon("listen");
    } catch (error) {
        cleanupRecorder();
        setCompanionState("error");
        setPanel(true);
        showToast("Microphone permission is needed. You can use the typed fallback.", true);
    }
}

function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;
    mediaRecorder.stop();
    elements.ptt.classList.remove("recording");
    elements.ptt.querySelector("strong").textContent = "Hold to talk";
}

function cleanupRecorder() {
    mediaStream?.getTracks().forEach(track => track.stop());
    mediaStream = null;
    mediaRecorder = null;
}

async function submitRecording() {
    const duration = performance.now() - recordingStartedAt;
    const type = audioChunks[0]?.type || mediaRecorder?.mimeType || "audio/webm";
    const blob = new Blob(audioChunks, { type });
    cleanupRecorder();
    if (duration < 280 || blob.size < 100) {
        setCompanionState("ready");
        elements.calmSubtitle.textContent = "Hold the talk button a little longer, then ask your question.";
        showToast("No usable speech was captured.", true);
        return;
    }
    setBusy(true);
    setCompanionState("thinking");
    elements.calmSubtitle.textContent = "Transcribing locally and checking the trusted state…";
    const stateSnapshot = client.selected.id;
    const sequence = ++requestSequence;
    await completeQuestion(client.askVoice(blob), stateSnapshot, sequence);
}

function bindInterface() {
    elements.panelToggle.addEventListener("click", () => setPanel(!elements.panel.classList.contains("open")));
    elements.closePanel.addEventListener("click", () => setPanel(false));
    elements.stateSelect.addEventListener("change", () => selectState(elements.stateSelect.value));
    elements.locale.addEventListener("change", () => client.setLocale(elements.locale.value));
    elements.ask.addEventListener("click", askTyped);
    elements.question.addEventListener("keydown", event => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") askTyped();
    });
    elements.audioToggle.addEventListener("change", () => {
        audio.setEnabled(elements.audioToggle.checked);
        if (!elements.audioToggle.checked) {
            audio.stopVoice();
            window.speechSynthesis?.cancel();
            setCompanionState("ready");
        }
    });
    elements.motionToggle.addEventListener("change", () => scene.setMotionEnabled(elements.motionToggle.checked));

    elements.ptt.addEventListener("pointerdown", event => {
        event.preventDefault();
        talkHeld = true;
        elements.ptt.setPointerCapture?.(event.pointerId);
        startRecording();
    });
    elements.ptt.addEventListener("pointerup", event => {
        event.preventDefault();
        talkHeld = false;
        stopRecording();
    });
    elements.ptt.addEventListener("pointercancel", () => {
        talkHeld = false;
        stopRecording();
    });
    elements.ptt.addEventListener("keydown", event => {
        if (!["Space", "Enter"].includes(event.code) || event.repeat) return;
        event.preventDefault();
        talkHeld = true;
        startRecording();
    });
    elements.ptt.addEventListener("keyup", event => {
        if (!["Space", "Enter"].includes(event.code)) return;
        event.preventDefault();
        talkHeld = false;
        stopRecording();
    });

    window.addEventListener("keydown", event => {
        if (event.code === "Escape" && elements.panel.classList.contains("open")) setPanel(false);
        if (event.code !== "Space" || event.repeat || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(document.activeElement?.tagName)) return;
        event.preventDefault();
        talkHeld = true;
        startRecording();
    });
    window.addEventListener("keyup", event => {
        if (event.code !== "Space") return;
        event.preventDefault();
        talkHeld = false;
        stopRecording();
    });

    document.querySelectorAll("[data-move]").forEach(button => {
        const direction = button.dataset.move;
        button.addEventListener("pointerdown", event => {
            event.preventDefault();
            button.setPointerCapture?.(event.pointerId);
            scene.setTouchMove(direction, true);
        });
        const stop = () => scene.setTouchMove(direction, false);
        button.addEventListener("pointerup", stop);
        button.addEventListener("pointercancel", stop);
        button.addEventListener("lostpointercapture", stop);
    });
    window.addEventListener("beforeunload", cleanupRecorder);
}

async function initialize() {
    bindInterface();
    elements.ptt.disabled = true;
    try {
        const scenarios = await client.initialize();
        populateStates(scenarios);
        selectState(scenarios[0].id);
        elements.apiDot.classList.add("online");
        elements.apiStatus.textContent = "Mission contract connected";
        showToast("KALMA classroom preview is ready.");
    } catch (error) {
        elements.apiDot.classList.add("offline");
        elements.apiStatus.textContent = "Mission unavailable";
        elements.objective.textContent = "Preview unavailable";
        elements.calmSubtitle.textContent = error.message;
        setCompanionState("error");
        showToast(error.message, true);
    }
}

initialize();
