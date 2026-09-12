# CALM AI Assistant

CALM is a context-aware safety assistant for a Grade 4 scenario-based VR
emergency-response learning environment. The current implementation separates
trusted VR state from learner speech, uses deterministic protocol selection for
critical instructions, and retrieves only curated protocol cards for educational
answers.

## Current status

| Component | Status |
|---|---|
| PDF/source audit | Complete for the current 20-PDF corpus |
| Curated protocol cards | 47 cards |
| EN / Filipino / Taglish retrieval units | 141 review-candidate units |
| Internal development gate | `INTERNAL_DEVELOPMENT_VALIDATED` |
| External/domain approval | Not yet completed |
| Production retrieval units | 0 (intentionally blocked) |
| School profile | Synthetic demo data; not school-approved |
| Unity scenario-to-corpus crosswalk | 8 missions / 55 implemented tasks validated |
| Local LLM/RAG chat | Ollama `qwen2.5:3b` connected at `POST /api/v1/chat` |
| Model selection | 3 models scored over 44 reviewed questions; see `docs/MODEL_BENCHMARK.md` |
| Question scope gating | Off-task and cross-hazard questions routed deterministically before retrieval |
| Speech in (STT) | `faster-whisper`, local only, at `POST /api/v1/voice-chat` |
| Speech out (TTS) | Philippine neural voices at `POST /api/v1/speak`; **requires network** |
| Router, mission-contract, API, RAG, crosswalk, scope, and speech tests | 174 passing |
| Browser test console | 16-state full-oracle matrix ready at `/`; text path does not load Whisper |
| Implemented end-to-end slice | Versioned 17-state school-earthquake mission contract |
| Unity assistant integration | Installed in 8 mission scenes; Typhoon School auto-walk passed 7/7 |

“Internally validated” means the corpus is suitable for prototype development,
VR integration testing, and preparation for UAT. It does **not** mean BFP,
PHIVOLCS, PAGASA, DepEd, local-DRRMO, or school approval, and it is not for a real
emergency.

## Run the prototype

Use the included Python 3.11 virtual environment:

```powershell
.\venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010`. The CALM Mission Control page lets you:

- choose trusted earthquake-state presets;
- keep one question while changing the state;
- edit the exact JSON context Unity will send;
- inspect protocol, action, route, assembly area, evidence, and decision trace;
- switch between English, Filipino, and Taglish; and
- run all 16 callable states as independent verification cases with exact
  wording, blocked-action, route, zone, movement, and mission-metadata checks.

Open `http://127.0.0.1:8010/simulation` for the learner-facing low-poly
classroom preview. It uses the 16-state mission contract for trusted state and
route authorization, and sends learner text or voice to `/api/v1/chat` or
`/api/v1/voice-chat`. It demonstrates first-person movement, KALMA's
listening/thinking/speaking states, both sides of the conversation, spatial
cover/hazard cues, route arrows, push-to-talk, earcons, and ambient ducking.

Open `http://127.0.0.1:8010/rag` for the local LLM/RAG test page. Choose any of
the 55 implemented Unity tasks, ask a question, and inspect the generated
answer, active task context, retrieved protocol IDs, model, and latency. Ollama
must be running locally. The defaults are:

```text
CALM_OLLAMA_URL=http://127.0.0.1:11434
CALM_OLLAMA_MODEL=qwen2.5:3b
```

The typed test path does not load the speech model, an LLM, or a GPU. The speech
model is loaded only when the separate voice endpoint is first used.

`CALM_WHISPER_DEVICE` defaults to `auto`: a CUDA model is built as a probe and
the GPU is used when that succeeds, because transcription is roughly eight times
faster there and the model fits alongside the language model. A machine without
CUDA, or without cuDNN beside the driver, falls back to the CPU rather than
failing. Force either with `CALM_WHISPER_DEVICE=cpu` or `=cuda`.

`CALM_WHISPER_MODEL` defaults to `small`. `base` mis-hears Filipino badly enough
to be unusable; `small` is the smallest size that transcribes it reliably. It is
downloaded on first use, and an offline machine falls back to whatever smaller
model is already cached.

### GPU acceleration

Answer latency depends almost entirely on whether Ollama reaches the GPU, and it
fails to that quietly. Confirm rather than assume:

```bash
curl -s http://127.0.0.1:11434/api/ps
```

A loaded model should report `size_vram` close to `size`. If `size_vram` is `0`,
Ollama is on the CPU and answers will be roughly three times slower. Two causes
seen on this project's development machine, both silent:

1. **GPU discovery hangs on an old integrated-GPU driver**, times out after ~95
   seconds, and Ollama then abandons every GPU including a healthy discrete one.
   Setting `OLLAMA_VULKAN=0` skips the probe that hangs.
2. **The CUDA backend fails to load against an old NVIDIA driver**, logged only
   as `load_backend: failed to load ... cuda_v12` in
   `%LOCALAPPDATA%\Ollama\server.log`. Updating the driver resolves it.

### Speech

Transcription is local. Synthesis is not: `POST /api/v1/speak` calls a Microsoft
neural-voice service, so it needs a network connection and it is the only step
in the pipeline that leaves the machine. Only text CALM itself authored is sent;
learner audio and learner questions never are. Synthesis failure returns 503 and
never blocks the answer, so a headset offline still gets its safety instruction
as text.

| Locale | Voice |
|---|---|
| `en-PH` | `en-PH-RosaNeural` (Philippine-accented English) |
| `fil-PH` | `fil-PH-BlessicaNeural` |
| `taglish-PH` | `fil-PH-BlessicaNeural` |

The deterministic mission-state endpoint is:

```text
POST /api/v1/respond
```

It accepts a learner question, locale, and a complete trusted context object.
See [school_earthquake_request.json](examples/school_earthquake_request.json).

Unity's KALMA assistant uses the conversational boundaries:

```text
POST /api/v1/chat
POST /api/v1/voice-chat
POST /api/v1/speak
```

`task_id` selects trusted task grounding. One completed previous exchange is
sent so short follow-ups such as “How?” can be answered in context; it is never
treated as route, mission, or safety authority.

On-task answers use the learner-agency order: immediate action, prohibited
boundary, then adult/responder handoff only when that part truly requires adult
authority or capability. Controlled practice props use crosswalk
`practice_steps` for “How?” instead of substituting a real-hazard “tell an
adult” instruction. See [KALMA Learner-Agency Policy](docs/LEARNER_AGENCY_POLICY.md).

Unity can list and retrieve the validated mission definition from:

```text
GET /api/v1/missions
GET /api/v1/missions/school-earthquake-minimal
```

The contract validates the canonical storyboard state, mission revision,
predecessor/event pair, adjacent sequence numbers, full state flags, alarm
meaning, route snapshot, and expected deterministic decision. Its API form also
includes an exact verification oracle derived from reviewed language packs and
deterministic fallbacks. See
[EQ School Unity Integration](docs/EQ_SCHOOL_UNITY_INTEGRATION.md).

The client transport, push-to-talk lifecycle, KALMA indicator, two-speaker
subtitles, voice playback, earcons, and ambient ducking are installed in all
eight current Unity mission scenes. The next milestones are Meta Quest headset
and microphone testing, partner-school configuration, authenticated deployment
transport, and domain/child-safety/language review. This is not production
readiness.

## Unity scenario crosswalk

[`config/unity_scenario_crosswalk.v1.json`](config/unity_scenario_crosswalk.v1.json)
maps every implemented Unity `task_id` to its hazard, setting, phase, trusted
flags, exact simulation instruction, and curated protocol-card IDs. The backend
loader returns these as two separate inputs for a future LLM/RAG generator:

- `active_simulation_instruction` describes the current Unity task;
- `retrieved_safety_evidence` contains the curated protocol cards that may
  ground the answer.

The mapping now feeds the local Ollama RAG generator. The learner-facing answer
is generated by `qwen2.5:3b`; task selection and evidence retrieval remain tied
to the trusted Unity `task_id`. Internal protocol metadata is returned
separately for verification and removed from the spoken learner text.

The RAG endpoint accepts:

```json
{
  "question": "Why should I go under the table?",
  "task_id": "eq_home_6_dch",
  "locale": "en-PH"
}
```

The conversational Unity transport is connected. A separate, complete trusted
state envelope is still used for the deterministic school-earthquake mission
contract; learner speech cannot mutate that state.

### Unity Editor and Meta Quest networking

The installed Unity client defaults to `http://127.0.0.1:8010`, which is correct
for Play Mode in the Windows Editor. On an Android headset, loopback points to
the headset itself. Use one of these explicitly:

- USB development: run `adb reverse tcp:8010 tcp:8010`, then enable
  `Allow Android Loopback For Adb Reverse` on `CalmClient`.
- Wi-Fi/LAN: start Uvicorn with `--host 0.0.0.0 --port 8010` and set `Base Url`
  to the teacher PC's reachable LAN address. Apply the school's firewall and
  network policy; do not expose the development service publicly.

An active OpenXR runtime and a real Quest headset/microphone are still required
for final device smoke testing. See
[the full-stack audit](docs/FULLSTACK_VR_AUDIT_2026-08-29.md).

## Verify

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe scripts\validate_corpus.py
.\venv\Scripts\python.exe scripts\validate_missions.py
.\venv\Scripts\python.exe scripts\validate_unity_crosswalk.py --unity-library "C:\CALM\CALM_VR\Assets\Scripts\Missions\MissionLibrary.cs"
.\venv\Scripts\python.exe -m scripts.audit_learner_agency --output reports\learner_agency_audit_2026-08-29.json
```

After editing card specifications, rebuild the generated artifacts first:

```powershell
.\venv\Scripts\python.exe scripts\build_protocol_cards.py
.\venv\Scripts\python.exe scripts\build_retrieval_units.py
```

## Safety architecture

1. Unity sends the trusted state: hazard, phase, place, learner action, active
   conditions, approved route/zone IDs, and authority state.
2. The deterministic router handles P0/P1 safety decisions and emits exact
   reviewed EN/FIL/Taglish text. It does not call an LLM.
3. Noncritical P2 questions search curated cards, never raw PDF chunks.
4. School alarms, routes, assembly areas, live route status, and reunification
   authorization remain deterministic local configuration/state and never enter
   embeddings or prompts.
5. The dashboard receives a minimized event without the question, raw voice,
   child name, address, medical details, or guardian identity.

See [School Local Configuration](docs/SCHOOL_LOCAL_CONFIGURATION.md) and
[Phase 2 Implementation](docs/PHASE2_IMPLEMENTATION.md).
