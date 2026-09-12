const MISSION_ID = "school-earthquake-minimal";
const MISSION_ENDPOINT = `/api/v1/missions/${MISSION_ID}`;

// The simulation contract has more fine-grained runtime states than the
// storyboard task list used by /api/v1/chat. Each state is therefore bound to
// the closest authoritative Unity task. The contract continues to own route
// authorization; this mapping is only the conversational grounding key.
const UNITY_TASK_FOR_STATE = Object.freeze({
    "EQ-S-B01": "eq_sch_3_cover",
    "EQ-S-B02": "eq_sch_3_cover",
    "EQ-S-B03": "eq_sch_2_route",
    "EQ-S-D01": "eq_sch_4_dch",
    "EQ-S-D02": "eq_sch_4_dch",
    "EQ-S-D03": "eq_sch_4_dch",
    "EQ-S-D04": "eq_sch_4_dch",
    "EQ-S-A01": "eq_sch_6_line",
    "EQ-S-A02": "eq_sch_6_line",
    "EQ-S-A03": "eq_sch_7_corridor",
    "EQ-S-H01-NO-ROUTE": "eq_sch_7_corridor",
    "EQ-S-A04": "eq_sch_9_assembly",
    "EQ-S-A05": "eq_sch_9_assembly",
    "EQ-S-A06": "eq_sch_8_aftershock",
    "EQ-S-A04R": "eq_sch_9_assembly",
    "EQ-S-A07": "eq_sch_9_assembly"
});

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function makeSessionId(stateId) {
    const token = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
    return `simulation-${stateId}-${token}`;
}

function incomingEdgeFor(contract, stateId, verification) {
    if (stateId === contract.initial_state_id) {
        return {
            previousStateId: null,
            transitionEvent: "MISSION_STARTED",
            stateSeq: 1,
            previousStateSeq: 0
        };
    }

    const entry = verification.entry ?? {};
    const configuredPrevious = verification.previous_state_id ?? entry.previous_state_id;
    const configuredEvent = verification.transition_event ?? entry.transition_event;
    if (configuredPrevious && configuredEvent) {
        return {
            previousStateId: configuredPrevious,
            transitionEvent: configuredEvent,
            stateSeq: 2,
            previousStateSeq: 1
        };
    }

    for (const [previousStateId, previousState] of Object.entries(contract.states)) {
        const transition = (previousState.transitions ?? []).find(item => item.to_state_id === stateId);
        if (transition) {
            return {
                previousStateId,
                transitionEvent: transition.event,
                stateSeq: 2,
                previousStateSeq: 1
            };
        }
    }
    throw new Error(`No reviewed transition reaches ${stateId}.`);
}

function audioExtension(mimeType) {
    if (mimeType.includes("ogg")) return "ogg";
    if (mimeType.includes("mp4")) return "m4a";
    if (mimeType.includes("mpeg")) return "mp3";
    return "webm";
}

export class CalmClient {
    constructor() {
        this.contract = null;
        this.scenarios = [];
        this.selected = null;
        this.locale = "en-PH";
        this.sessionId = makeSessionId("conversation");
        this.previousQuestion = null;
        this.previousResponse = null;
    }

    async initialize() {
        const response = await fetch(MISSION_ENDPOINT, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`Mission contract failed to load (${response.status}).`);
        this.contract = await response.json();
        this.scenarios = this.buildScenarios(this.contract);
        if (!this.scenarios.length) throw new Error("Mission contains no previewable states.");
        this.selectState(this.scenarios[0].id);
        return this.scenarios;
    }

    buildScenarios(contract) {
        const verificationStates = contract.verification?.states;
        const stateOrder = contract.verification?.callable_state_order ?? Object.keys(verificationStates ?? {});
        if (!verificationStates || !Array.isArray(stateOrder)) {
            throw new Error("Mission verification metadata is incomplete.");
        }

        return stateOrder.map(stateId => {
            const state = contract.states[stateId];
            const verification = verificationStates[stateId];
            if (!state || !verification || state.kind === "terminal") {
                throw new Error(`Mission references an invalid preview state: ${stateId}.`);
            }
            const incoming = incomingEdgeFor(contract, stateId, verification);
            const context = {
                ...clone(contract.base_context),
                ...clone(state.context_patch),
                session_id: makeSessionId(stateId),
                scenario_id: contract.mission_id,
                mission_revision: contract.mission_revision,
                state_id: stateId,
                state_seq: incoming.stateSeq,
                previous_state_seq: incoming.previousStateSeq,
                previous_state_id: incoming.previousStateId,
                transition_event: incoming.transitionEvent,
                timestamp: new Date().toISOString()
            };

            return {
                id: stateId,
                label: state.label,
                kind: state.kind,
                taskId: UNITY_TASK_FOR_STATE[stateId],
                protocolId: state.calm.protocol_id,
                actionCode: state.calm.action_code,
                context,
                expectedMovement: verification.expected_movement_authorized === true,
                expectedRoute: verification.expected_selected_route_id ?? null,
                expectedZone: verification.expected_safe_zone_id ?? null
            };
        });
    }

    selectState(stateId) {
        const next = this.scenarios.find(item => item.id === stateId);
        if (!next) throw new Error(`Unknown mission state: ${stateId}`);
        if (!next.taskId) throw new Error(`Mission state has no Unity task mapping: ${stateId}`);
        this.selected = next;
        this.previousQuestion = null;
        this.previousResponse = null;
        return next;
    }

    setLocale(locale) {
        this.locale = locale;
    }

    contextSnapshot() {
        if (!this.selected) throw new Error("Mission state is not ready.");
        const context = clone(this.selected.context);
        context.session_id = makeSessionId(this.selected.id);
        context.timestamp = new Date().toISOString();
        return context;
    }

    async ask(question) {
        if (!this.selected?.taskId) throw new Error("Unity task mapping is not ready.");
        const body = {
            question,
            task_id: this.selected.taskId,
            locale: this.locale,
            session_id: this.sessionId
        };
        if (this.previousQuestion && this.previousResponse) {
            body.previous_question = this.previousQuestion;
            body.previous_response = this.previousResponse;
        }
        const response = await fetch("/api/v1/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify(body)
        });
        const result = await this.readJson(response, "KALMA answer");
        this.rememberTurn(question, result.response_text);
        return result;
    }

    async askVoice(audioBlob) {
        if (!this.selected?.taskId) throw new Error("Unity task mapping is not ready.");
        const form = new FormData();
        form.append(
            "audio_file",
            audioBlob,
            `learner-question.${audioExtension(audioBlob.type || "audio/webm")}`
        );
        form.append("task_id", this.selected.taskId);
        form.append("locale", this.locale);
        form.append("session_id", this.sessionId);
        if (this.previousQuestion && this.previousResponse) {
            form.append("previous_question", this.previousQuestion);
            form.append("previous_response", this.previousResponse);
        }

        const response = await fetch("/api/v1/voice-chat", {
            method: "POST",
            body: form,
            headers: { Accept: "application/json" }
        });
        const result = await this.readJson(response, "Voice question");
        this.rememberTurn(result.transcript ?? result.question, result.response_text);
        return result;
    }

    rememberTurn(question, response) {
        this.previousQuestion = question?.trim() || null;
        this.previousResponse = response?.trim() || null;
        if (!this.previousQuestion || !this.previousResponse) {
            this.previousQuestion = null;
            this.previousResponse = null;
        }
    }

    async speak(text) {
        const response = await fetch("/api/v1/speak", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "audio/mpeg" },
            body: JSON.stringify({ text, locale: this.locale })
        });
        if (!response.ok) {
            let detail = `Speech synthesis failed (${response.status}).`;
            try {
                const payload = await response.json();
                detail = payload.detail ?? detail;
            } catch {
                // Keep the status-based fallback.
            }
            throw new Error(detail);
        }
        return response.blob();
    }

    async readJson(response, label) {
        let payload;
        try {
            payload = await response.json();
        } catch {
            throw new Error(`${label} returned an unreadable response.`);
        }
        if (!response.ok) {
            const detail = Array.isArray(payload.detail)
                ? payload.detail.map(item => item.msg).join("; ")
                : payload.detail;
            throw new Error(detail || `${label} failed (${response.status}).`);
        }
        return payload;
    }
}
