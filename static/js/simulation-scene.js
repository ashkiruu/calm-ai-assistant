const COLORS = {
    safe: "#72dea4",
    caution: "#f4c95d",
    danger: "#ff6b6b",
    cyan: "#49d9f5"
};

const STATE_VISUALS = {
    "EQ-S-B01": { phase: "Before", scene: "Classroom A", safe: ["desk-center"], hint: "Find the sturdy desk nearest to you." },
    "EQ-S-B02": { phase: "Before", scene: "Classroom A", caution: ["cabinet"], hint: "Notice and report the unsecured cabinet." },
    "EQ-S-B03": { phase: "Before", scene: "Classroom A", route: "preview", hint: "Learn the marked route; do not evacuate yet." },
    "EQ-S-D01": { phase: "During", scene: "Classroom A", safe: ["desk-center"], shaking: true, hint: "Move under the highlighted sturdy desk." },
    "EQ-S-D02": { phase: "During", scene: "Classroom A", safe: ["desk-center"], danger: ["exit"], shaking: true, hint: "The exit is unsafe while the ground is shaking." },
    "EQ-S-D03": { phase: "During", scene: "Classroom A", safe: ["desk-center"], danger: ["windows", "cabinet"], shaking: true, hint: "Move away from glass and falling objects." },
    "EQ-S-D04": { phase: "During", scene: "Classroom A", safe: ["desk-center"], shaking: true, hint: "Stay protected until shaking stops." },
    "EQ-S-A01": { phase: "After", scene: "Classroom A", hint: "Stay with the class and wait for the teacher." },
    "EQ-S-A02": { phase: "After", scene: "Classroom exit", route: "active", hint: "The teacher-approved alternate route is ready." },
    "EQ-S-A03": { phase: "After", scene: "Evacuation corridor", route: "active", hint: "Walk—do not run—along the green route." },
    "EQ-S-H01-NO-ROUTE": { phase: "After", scene: "Classroom exit", danger: ["exit"], hint: "No approved route is open. Hold with the teacher." },
    "EQ-S-A04": { phase: "After", scene: "Assembly A", safe: ["assembly"], hint: "Remain inside the assembly zone for headcount." },
    "EQ-S-A05": { phase: "After", scene: "Assembly A", safe: ["teacher"], hint: "Report the fictional missing classmate to the teacher." },
    "EQ-S-A06": { phase: "Aftershock", scene: "Assembly A", safe: ["assembly-cover"], shaking: true, hint: "Stop and protect again during the aftershock." },
    "EQ-S-A04R": { phase: "After", scene: "Assembly A", safe: ["assembly"], hint: "Return to the class group and resume headcount." },
    "EQ-S-A07": { phase: "After", scene: "Assembly A", danger: ["exit"], hint: "Do not re-enter before official clearance." }
};

const TELEPORTS = {
    "EQ-S-B01": { x: 0, z: 2.4, yaw: 0 },
    "EQ-S-B02": { x: 2.2, z: 4.5, yaw: 0.38 },
    "EQ-S-B03": { x: 0, z: 7, yaw: 0 },
    "EQ-S-D01": { x: 0, z: 4.4, yaw: 0 },
    "EQ-S-D02": { x: 0, z: 9.4, yaw: 0 },
    "EQ-S-D03": { x: -3.7, z: 7, yaw: -1.2 },
    "EQ-S-D04": { x: 0, z: 6.2, yaw: 0 },
    "EQ-S-A01": { x: 0, z: 8.4, yaw: 0 },
    "EQ-S-A02": { x: 0, z: 10.8, yaw: 0 },
    "EQ-S-A03": { x: 0, z: 15.5, yaw: 0 },
    "EQ-S-H01-NO-ROUTE": { x: 0, z: 10.8, yaw: 0 },
    "EQ-S-A04": { x: 0, z: 27, yaw: 0 },
    "EQ-S-A05": { x: 0.8, z: 28, yaw: 0.18 },
    "EQ-S-A06": { x: 0, z: 27.5, yaw: 0 },
    "EQ-S-A04R": { x: 0, z: 27, yaw: 0 },
    "EQ-S-A07": { x: 0, z: 31, yaw: Math.PI }
};

function shade(hex, factor) {
    const value = Number.parseInt(hex.slice(1), 16);
    const r = Math.max(0, Math.min(255, Math.round(((value >> 16) & 255) * factor)));
    const g = Math.max(0, Math.min(255, Math.round(((value >> 8) & 255) * factor)));
    const b = Math.max(0, Math.min(255, Math.round((value & 255) * factor)));
    return `rgb(${r}, ${g}, ${b})`;
}

function distance2d(a, b) {
    return Math.hypot(a.x - b.x, a.z - b.z);
}

export class LowPolyScene {
    constructor(canvas, { onAlert } = {}) {
        this.canvas = canvas;
        this.context = canvas.getContext("2d");
        this.onAlert = onAlert;
        this.width = 0;
        this.height = 0;
        this.camera = { x: 0, y: 1.62, z: 2.4, yaw: 0 };
        this.keys = new Set();
        this.touchMoves = new Set();
        this.stateId = null;
        this.visual = STATE_VISUALS["EQ-S-B01"];
        this.motionEnabled = true;
        this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
        this.lastTime = performance.now();
        this.alertKey = "";
        this.pointerStart = null;
        this.objects = this.buildWorld();
        this.routes = this.buildRoutes();
        this.bindControls();
        this.resize();
        requestAnimationFrame(time => this.frame(time));
    }

    buildWorld() {
        const objects = [
            { id: "back-wall-left", type: "wall", x: -4.6, z: 13.7, w: 4.8, d: 0.24, h: 3.3, color: "#c2bdb2" },
            { id: "back-wall-right", type: "wall", x: 4.6, z: 13.7, w: 4.8, d: 0.24, h: 3.3, color: "#c2bdb2" },
            { id: "left-wall", type: "wall", x: -7, z: 7.1, w: 0.2, d: 13.4, h: 3.3, color: "#b5b0a6" },
            { id: "right-wall", type: "wall", x: 7, z: 7.1, w: 0.2, d: 13.4, h: 3.3, color: "#b5b0a6" },
            { id: "exit", type: "exit", x: 0, z: 13.72, w: 2.3, d: 0.3, h: 2.55, color: "#263b64" },
            { id: "cabinet", type: "cabinet", x: 5.65, z: 9.5, w: 1.45, d: 0.75, h: 2.45, color: "#a86f45" },
            { id: "teacher", type: "teacher", x: 1.4, z: 31.5, w: 0.55, d: 0.55, h: 1.7, color: "#397f8b" },
            { id: "assembly-cover", type: "cover", x: -3.8, z: 32.8, w: 2.4, d: 1.2, h: 0.85, color: "#547d72" }
        ];

        for (const z of [5.2, 8.1, 11]) {
            for (const x of [-3.3, 0, 3.3]) {
                const center = x === 0 && z === 8.1;
                objects.push({
                    id: center ? "desk-center" : `desk-${x}-${z}`,
                    type: "desk",
                    x,
                    z,
                    w: 2.15,
                    d: 1.1,
                    h: 0.78,
                    color: center ? "#376f75" : "#537d80"
                });
            }
        }

        for (const z of [4.8, 8.1, 11.1]) {
            objects.push({ id: `window-${z}`, group: "windows", type: "window", x: -6.88, z, w: 0.12, d: 2.2, h: 1.35, y: 1.05, color: "#64afc2" });
        }

        for (const x of [-4.2, -2.1, 0, 2.1, 4.2]) {
            objects.push({ id: `assembly-${x}`, group: "assembly", type: "marker", x, z: 34.6, w: 1.25, d: 0.35, h: 0.12, color: "#5b8a70" });
        }
        return objects;
    }

    buildRoutes() {
        const points = [];
        for (let z = 9.5; z <= 33; z += 1.65) {
            const bend = z > 18 ? Math.min(2.2, (z - 18) * 0.13) : 0;
            points.push({ x: bend, z });
        }
        return points;
    }

    bindControls() {
        window.addEventListener("resize", () => this.resize());
        window.addEventListener("keydown", event => {
            if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
            if (["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) {
                event.preventDefault();
                this.keys.add(event.code);
            }
        });
        window.addEventListener("keyup", event => this.keys.delete(event.code));
        window.addEventListener("blur", () => this.keys.clear());

        this.canvas.addEventListener("click", () => {
            if (matchMedia("(pointer: fine)").matches && document.pointerLockElement !== this.canvas) {
                this.canvas.requestPointerLock?.();
            }
        });
        document.addEventListener("mousemove", event => {
            if (document.pointerLockElement === this.canvas) {
                this.camera.yaw += event.movementX * 0.0022;
            }
        });
        this.canvas.addEventListener("pointerdown", event => {
            if (event.pointerType !== "mouse") this.pointerStart = { x: event.clientX, yaw: this.camera.yaw };
        });
        this.canvas.addEventListener("pointermove", event => {
            if (this.pointerStart && event.pointerType !== "mouse") {
                this.camera.yaw = this.pointerStart.yaw + (event.clientX - this.pointerStart.x) * 0.005;
            }
        });
        const endPointer = () => { this.pointerStart = null; };
        this.canvas.addEventListener("pointerup", endPointer);
        this.canvas.addEventListener("pointercancel", endPointer);
    }

    setTouchMove(direction, active) {
        if (active) this.touchMoves.add(direction);
        else this.touchMoves.delete(direction);
    }

    setMotionEnabled(enabled) {
        this.motionEnabled = enabled;
    }

    setState(stateId) {
        this.stateId = stateId;
        this.visual = STATE_VISUALS[stateId] ?? STATE_VISUALS["EQ-S-B01"];
        const teleport = TELEPORTS[stateId];
        if (teleport) Object.assign(this.camera, teleport);
        this.alertKey = "";
        this.onAlert?.(null);
        return this.visual;
    }

    setResponse(result) {
        if (result?.movement_authorized && result.selected_route_id) {
            this.visual = { ...this.visual, route: "active" };
        }
        if (result?.context_status && result.context_status !== "valid") {
            this.visual = { ...this.visual, route: null, danger: ["exit"] };
        }
    }

    resize() {
        const bounds = this.canvas.getBoundingClientRect();
        const ratio = Math.min(devicePixelRatio || 1, 2);
        this.width = Math.max(1, bounds.width);
        this.height = Math.max(1, bounds.height);
        this.canvas.width = Math.round(this.width * ratio);
        this.canvas.height = Math.round(this.height * ratio);
        this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    frame(time) {
        const delta = Math.min(0.04, (time - this.lastTime) / 1000);
        this.lastTime = time;
        this.update(delta);
        this.render(time);
        requestAnimationFrame(next => this.frame(next));
    }

    update(delta) {
        const forward = this.keys.has("KeyW") || this.keys.has("ArrowUp") || this.touchMoves.has("forward");
        const backward = this.keys.has("KeyS") || this.keys.has("ArrowDown") || this.touchMoves.has("backward");
        const left = this.keys.has("KeyA") || this.keys.has("ArrowLeft") || this.touchMoves.has("left");
        const right = this.keys.has("KeyD") || this.keys.has("ArrowRight") || this.touchMoves.has("right");
        const speed = 3.5 * delta;
        const longitudinal = Number(forward) - Number(backward);
        const lateral = Number(right) - Number(left);
        if (longitudinal || lateral) {
            const length = Math.hypot(longitudinal, lateral) || 1;
            const f = longitudinal / length;
            const s = lateral / length;
            this.camera.x += (Math.sin(this.camera.yaw) * f + Math.cos(this.camera.yaw) * s) * speed;
            this.camera.z += (Math.cos(this.camera.yaw) * f - Math.sin(this.camera.yaw) * s) * speed;
            this.camera.x = Math.max(-6.4, Math.min(6.4, this.camera.x));
            this.camera.z = Math.max(1, Math.min(37, this.camera.z));
        }
        this.checkProximity();
    }

    checkProximity() {
        const hazards = [];
        for (const object of this.objects) {
            const highlighted = this.highlightKind(object);
            if (!highlighted || !["danger", "caution"].includes(highlighted)) continue;
            if (distance2d(this.camera, object) < (object.type === "window" ? 2.6 : 2.3)) {
                hazards.push({ object, kind: highlighted });
            }
        }
        const nearest = hazards.sort((a, b) => distance2d(this.camera, a.object) - distance2d(this.camera, b.object))[0];
        const key = nearest ? `${nearest.object.id}:${nearest.kind}` : "";
        if (key === this.alertKey) return;
        this.alertKey = key;
        if (!nearest) {
            this.onAlert?.(null);
            return;
        }
        const messages = {
            window: "Move away from glass.",
            cabinet: nearest.kind === "danger" ? "Move away from falling objects." : "Report this unsecured cabinet.",
            exit: "This exit is not authorized right now."
        };
        this.onAlert?.({ kind: nearest.kind, text: messages[nearest.object.type] ?? "Keep away from this area." });
    }

    project(point) {
        const dx = point.x - this.camera.x;
        const dz = point.z - this.camera.z;
        const dy = point.y - this.camera.y;
        const cos = Math.cos(this.camera.yaw);
        const sin = Math.sin(this.camera.yaw);
        const cameraX = dx * cos - dz * sin;
        const cameraZ = dx * sin + dz * cos;
        if (cameraZ <= 0.16) return null;
        const focal = Math.min(this.width, this.height) * 0.86;
        return {
            x: this.width * 0.5 + cameraX * focal / cameraZ,
            y: this.height * 0.53 - dy * focal / cameraZ,
            z: cameraZ
        };
    }

    polygon(points, fill, stroke = null, lineWidth = 1) {
        const projected = points.map(point => this.project(point));
        if (projected.some(point => !point)) return null;
        const context = this.context;
        context.beginPath();
        context.moveTo(projected[0].x, projected[0].y);
        projected.slice(1).forEach(point => context.lineTo(point.x, point.y));
        context.closePath();
        if (fill) { context.fillStyle = fill; context.fill(); }
        if (stroke) { context.strokeStyle = stroke; context.lineWidth = lineWidth; context.stroke(); }
        return projected.reduce((sum, point) => sum + point.z, 0) / projected.length;
    }

    boxFaces(object) {
        const y0 = object.y ?? 0;
        const y1 = y0 + object.h;
        const x0 = object.x - object.w / 2;
        const x1 = object.x + object.w / 2;
        const z0 = object.z - object.d / 2;
        const z1 = object.z + object.d / 2;
        const p = {
            a: { x: x0, y: y0, z: z0 }, b: { x: x1, y: y0, z: z0 },
            c: { x: x1, y: y0, z: z1 }, d: { x: x0, y: y0, z: z1 },
            e: { x: x0, y: y1, z: z0 }, f: { x: x1, y: y1, z: z0 },
            g: { x: x1, y: y1, z: z1 }, h: { x: x0, y: y1, z: z1 }
        };
        return [
            { points: [p.a, p.b, p.f, p.e], color: shade(object.color, 0.84) },
            { points: [p.b, p.c, p.g, p.f], color: shade(object.color, 0.68) },
            { points: [p.c, p.d, p.h, p.g], color: shade(object.color, 0.76) },
            { points: [p.d, p.a, p.e, p.h], color: shade(object.color, 0.62) },
            { points: [p.e, p.f, p.g, p.h], color: shade(object.color, 1.06) }
        ];
    }

    faceDepth(points) {
        const cos = Math.cos(this.camera.yaw);
        const sin = Math.sin(this.camera.yaw);
        return points.reduce((sum, point) => {
            const dx = point.x - this.camera.x;
            const dz = point.z - this.camera.z;
            return sum + dx * sin + dz * cos;
        }, 0) / points.length;
    }

    highlightKind(object) {
        const groups = [object.id, object.group].filter(Boolean);
        if (groups.some(id => this.visual.danger?.includes(id))) return "danger";
        if (groups.some(id => this.visual.caution?.includes(id))) return "caution";
        if (groups.some(id => this.visual.safe?.includes(id))) return "safe";
        return null;
    }

    render(time) {
        const context = this.context;
        context.clearRect(0, 0, this.width, this.height);
        this.drawSky();

        const shaking = this.visual.shaking && this.motionEnabled && !this.reducedMotion;
        const shakeX = shaking ? Math.sin(time * 0.047) * 2.2 + Math.sin(time * 0.113) * 0.9 : 0;
        const shakeY = shaking ? Math.cos(time * 0.059) * 1.6 : 0;
        context.save();
        context.translate(shakeX, shakeY);
        this.drawGround();
        this.drawRoute(time);

        const faces = [];
        for (const object of this.objects) {
            for (const face of this.boxFaces(object)) {
                faces.push({ ...face, depth: this.faceDepth(face.points), object });
            }
        }
        faces.sort((a, b) => b.depth - a.depth);
        for (const face of faces) {
            if (face.depth > 0.12) this.polygon(face.points, face.color, "rgba(7,25,35,0.18)", 0.7);
        }
        this.drawHighlights(time);
        this.drawLabels();
        context.restore();
    }

    drawSky() {
        const context = this.context;
        context.fillStyle = "#9bb9dc";
        context.fillRect(0, 0, this.width, this.height * 0.58);
        context.fillStyle = "#c9c4ba";
        context.beginPath();
        context.moveTo(0, this.height * 0.47);
        for (let x = 0; x <= this.width; x += this.width / 7) {
            const offset = Math.sin(x * 0.018 + this.camera.yaw) * 25;
            context.lineTo(x, this.height * 0.39 + offset);
        }
        context.lineTo(this.width, this.height * 0.58);
        context.lineTo(0, this.height * 0.58);
        context.fill();
    }

    drawGround() {
        this.polygon(
            [{ x: -12, y: 0, z: 0 }, { x: 12, y: 0, z: 0 }, { x: 12, y: 0, z: 42 }, { x: -12, y: 0, z: 42 }],
            "#b68d69"
        );
        const context = this.context;
        context.save();
        context.globalAlpha = 0.22;
        for (let z = 1; z <= 40; z += 2) {
            this.polygon([{ x: -7, y: 0.008, z }, { x: 7, y: 0.008, z }], null, "#dce7df", 0.7);
        }
        for (let x = -6; x <= 6; x += 2) {
            this.polygon([{ x, y: 0.008, z: 1 }, { x, y: 0.008, z: 40 }], null, "#dce7df", 0.7);
        }
        context.restore();

        this.polygon(
            [{ x: -5.8, y: 0.012, z: 26 }, { x: 5.8, y: 0.012, z: 26 }, { x: 5.8, y: 0.012, z: 36.5 }, { x: -5.8, y: 0.012, z: 36.5 }],
            "rgba(80, 122, 91, 0.42)",
            "rgba(114, 222, 164, 0.38)",
            1.5
        );
    }

    drawRoute(time) {
        if (!this.visual.route) return;
        const context = this.context;
        const color = this.visual.route === "active" ? COLORS.safe : COLORS.caution;
        const pulse = 0.48 + Math.sin(time * 0.004) * 0.14;
        context.save();
        context.globalAlpha = pulse;
        context.shadowColor = color;
        context.shadowBlur = 12;
        for (const point of this.routes) {
            const half = 0.34;
            this.polygon([
                { x: point.x, y: 0.035, z: point.z + 0.55 },
                { x: point.x + half, y: 0.035, z: point.z },
                { x: point.x + 0.14, y: 0.035, z: point.z + 0.08 },
                { x: point.x + 0.14, y: 0.035, z: point.z - 0.42 },
                { x: point.x - 0.14, y: 0.035, z: point.z - 0.42 },
                { x: point.x - 0.14, y: 0.035, z: point.z + 0.08 },
                { x: point.x - half, y: 0.035, z: point.z }
            ], color);
        }
        context.restore();
    }

    drawHighlights(time) {
        const context = this.context;
        const pulse = 0.62 + Math.sin(time * 0.005) * 0.18;
        for (const object of this.objects) {
            const kind = this.highlightKind(object);
            if (!kind) continue;
            const color = COLORS[kind];
            context.save();
            context.globalAlpha = pulse;
            context.strokeStyle = color;
            context.lineWidth = kind === "danger" ? 2.4 : 2;
            context.shadowColor = color;
            context.shadowBlur = kind === "danger" ? 22 : 16;
            for (const face of this.boxFaces(object)) this.polygon(face.points, null, color, context.lineWidth);
            context.restore();
        }
    }

    drawLabels() {
        const labels = [];
        for (const object of this.objects) {
            const kind = this.highlightKind(object);
            if (!kind) continue;
            const point = this.project({ x: object.x, y: (object.y ?? 0) + object.h + 0.28, z: object.z });
            if (!point || point.z > 18) continue;
            const names = {
                desk: "SAFE COVER",
                cabinet: kind === "danger" ? "FALLING HAZARD" : "REPORT HAZARD",
                window: "GLASS HAZARD",
                exit: "DO NOT ENTER",
                marker: "ASSEMBLY A",
                teacher: "TEACHER",
                cover: "RE-PROTECT"
            };
            labels.push({ ...point, text: names[object.type] ?? "SAFETY CUE", color: COLORS[kind] });
        }
        labels.sort((a, b) => b.z - a.z);
        for (const label of labels) {
            const context = this.context;
            context.save();
            context.font = "700 10px Cascadia Code, monospace";
            const width = context.measureText(label.text).width + 14;
            context.fillStyle = "rgba(7,25,35,0.82)";
            context.fillRect(label.x - width / 2, label.y - 20, width, 18);
            context.strokeStyle = label.color;
            context.strokeRect(label.x - width / 2, label.y - 20, width, 18);
            context.fillStyle = label.color;
            context.textAlign = "center";
            context.fillText(label.text, label.x, label.y - 7);
            context.restore();
        }
    }
}

export function visualForState(stateId) {
    return STATE_VISUALS[stateId] ?? STATE_VISUALS["EQ-S-B01"];
}
