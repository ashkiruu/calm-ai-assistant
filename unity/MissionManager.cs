using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using CALM.Hazards;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace CALM.Missions
{
    /// <summary>
    /// Runs a MissionDefinition. Phases always run in order (BEFORE -> DURING ->
    /// AFTER, Appendix B item 1). Within a phase, tasks run one at a time unless
    /// the phase is marked FreeOrder, in which case every task whose prerequisites
    /// are met arms at once and they may be finished in any order.
    ///
    /// A wrong action never blocks, fails or skips — it plays a corrective line
    /// and leaves the same task armed (thesis delimitation).
    /// </summary>
    public class MissionManager : MonoBehaviour
    {
        public static MissionManager Instance { get; private set; }

        public event Action<MissionPhase> PhaseStarted;
        public event Action<MissionPhase> PhaseRetried;
        public event Action<MissionDefinition> BriefingStarted;
        public event Action<TaskDefinition> TaskStarted;
        public event Action<TaskDefinition> TaskCompleted;
        public event Action<MissionResult> MissionCompleted;

        /// <summary>One armed task: its definition, its condition, and the host it lives on.</summary>
        class TaskRun
        {
            public TaskDefinition Def;
            public GameObject Host;
            public TaskCondition Cond;
            public bool Done;
            /// Position in the flattened mission task list — the step-dot index and
            /// the "furthest reached" marker. NOT a completion counter: in a free
            /// order phase those two are different numbers.
            public int Index;
            /// Resolved target transforms, for picking which armed task the HUD shows.
            public readonly List<Transform> Focusables = new List<Transform>();
        }

        MissionDefinition _mission;
        MissionContext _ctx;
        MissionHUD _hud;
        MissionBoard _board;
        IGuidanceProvider _guide;

        readonly List<TaskRun> _armed = new List<TaskRun>();
        readonly HashSet<GameObject> _armedTargets = new HashSet<GameObject>();
        readonly List<string> _completedIds = new List<string>();
        readonly Dictionary<string, int> _indexById = new Dictionary<string, int>();
        TaskRun _focus;
        float _focusNextEval;

        int _infractions;
        int _timersMissed;
        float _startTime;
        bool _running;

        // Phase timer state. Deadline < 0 means no timer running.
        float _timerDeadline = -1f;
        MissionPhase _timerPhase;
        bool _phaseRetryRequested;
        TeleportPaceMonitor _pace;
        int _paceHolders;

        /// <summary>The task the HUD is currently showing. In a sequential phase
        /// that is the only armed task; in a free-order phase it is whichever one
        /// the learner appears to be working on.</summary>
        public TaskCondition ActiveCondition => _focus != null ? _focus.Cond : null;
        public TaskDefinition ActiveTask => _focus != null ? _focus.Def : null;
        /// <summary>Every task armed right now. The auto-walk harness drives a
        /// specific one of these rather than assuming there is only one.</summary>
        public IEnumerable<TaskDefinition> ArmedTasks => _armed.Where(r => !r.Done).Select(r => r.Def);

        /// <summary>The live condition for a given task id, or null if not armed.</summary>
        public TaskCondition ConditionFor(string taskId)
        {
            var run = _armed.FirstOrDefault(r => r.Def.Id == taskId);
            return run != null ? run.Cond : null;
        }

        public MissionDefinition Mission => _mission;
        public IReadOnlyList<string> CompletedTaskIds => _completedIds;
        public int Infractions => _infractions;

        void Awake() => Instance = this;

        IEnumerator Start()
        {
            string scene = SceneManager.GetActiveScene().name;
            _mission = MissionLibrary.GetMission(scene);
            if (_mission == null)
            {
                Debug.Log($"CALM_MISSION: no mission defined for scene '{scene}' — manager idle.");
                yield break;
            }

            var head = Camera.main != null ? Camera.main.transform : null;
            if (head == null)
            {
                Debug.LogError("CALM_MISSION: no Main Camera — cannot run mission.");
                yield break;
            }

            _hud = MissionHUD.Create(head);

            // Banner + checklist go on a wall board so they never sit in the
            // learner's line of sight. Missions without an anchor simply run
            // without one — the instruction on the HUD is what's load-bearing.
            var anchor = GameObject.Find("MissionBoardAnchor");
            if (anchor != null) _board = MissionBoard.Create(anchor.transform);
            else Debug.LogWarning("CALM_MISSION: no 'MissionBoardAnchor' in scene — running without the wall board.");

            var stub = gameObject.GetComponent<GuidanceStub>() ?? gameObject.AddComponent<GuidanceStub>();
            stub.Hud = _hud;
            _guide = stub;

            _ctx = new MissionContext
            {
                Head = head,
                OverheadAnchor = EnsureAnchor(head, "OverheadAnchor", new Vector3(0f, 0.28f, 0.10f)),
                FaceAnchor = EnsureAnchor(head, "FaceAnchor", new Vector3(0f, -0.06f, 0.16f)),
                Guide = _guide,
                Hud = _hud,
                Resolve = ResolveByName,
                IsClaimedElsewhere = go => _armedTargets.Contains(go),
            };

            if (!VerifySceneNames()) yield break;
            WarnAboutFreeOrderHazards();

            var allTasks = _mission.Phases.SelectMany(p => p.Tasks).ToList();
            _indexById.Clear();
            for (int i = 0; i < allTasks.Count; i++) _indexById[allTasks[i].Id] = i;

            if (_board != null) _board.SetChecklist(allTasks);
            _hud.BuildSteps(allTasks.Count);
            _hud.SetStepStates(new HashSet<int>(), new HashSet<int>());
            HideRevealOnArmObjects();

            MissionProgress.MissionStarted(scene, _mission.TotalTasks);

            // BRIEFING. Carries the mission's Setup line, its prologue and its
            // phase agenda, and waits for the learner to press I'M READY. The
            // prologue is deliberately NOT also spoken to the subtitle strip: it
            // has already been read here, and re-queueing it would delay the
            // first task's line by the length of the whole paragraph.
            //
            // The HUD bar rides at 1.35 m and the panel at 1.9 m, so the bar sits
            // IN FRONT of the panel and covered both the agenda and the I'M READY
            // button. Nothing else is competing for the learner's attention during
            // the briefing anyway, so the bar stands down until the mission starts.
            // The assistant uses this non-authoritative signal to warm the first
            // grounded answer while the learner reads. Mission state still stays
            // entirely inside MissionManager and its deterministic guide.
            BriefingStarted?.Invoke(_mission);
            _hud.Hide();
            var briefing = MissionBriefingPanel.Show(head, _mission);
            while (briefing != null && !briefing.Dismissed) yield return null;
            _hud.Show();

            // The clock starts when the mission does, not when the reading does.
            _startTime = Time.time;
            _running = true;

            foreach (var phase in _mission.Phases)
                yield return RunPhase(phase);

            _running = false;

            var result = new MissionResult
            {
                TasksCompleted = _completedIds.Count,
                TasksTotal = _mission.TotalTasks,
                Infractions = _infractions,
                TimersMissed = _timersMissed,
                Seconds = Time.time - _startTime,
            };
            Debug.Log($"CALM_MISSION: complete — {result.TasksCompleted}/{result.TasksTotal} tasks, " +
                      $"{result.Infractions} corrections, {result.Seconds:F1}s, {result.Stars} stars.");
            MissionProgress.MissionCompleted(_mission.SceneName, result);
            MissionCompleted?.Invoke(result);

            _hud.Hide();

            // DEBRIEF, then the score. The completion line used to be spoken at
            // the same moment the HUD was destroyed, so the closing lesson of
            // every mission was unreadable.
            var debrief = MissionDebriefPanel.Show(_ctx.Head, _mission, _completedIds);
            while (debrief != null && !debrief.Dismissed) yield return null;

            MissionResultsPanel.Show(_ctx.Head, result, _mission.Title);
        }

        IEnumerator RunPhase(MissionPhase phase)
        {
            if (_board != null) _board.SetBanner(phase.Banner);
            PhaseStarted?.Invoke(phase);

            bool retrying = false;
            do
            {
                _phaseRetryRequested = false;
                HazardDirector.Trigger(phase.EventOnEnter);

                string intro = retrying ? phase.RetryLineId : phase.IntroLineId;
                if (!string.IsNullOrEmpty(intro))
                {
                    _guide.Speak(intro);
                    // Wait for the line to actually be READ, not a hardcoded 0.6 s.
                    yield return WaitForGuide(4f);
                }

                // The countdown starts at phase entry unless a specific task
                // claims it ("⏱ 2:00 starts at row 6").
                bool timerDeferred = phase.Tasks.Any(t => t.StartsPhaseTimer);
                if (phase.TimerSeconds > 0f && !timerDeferred) StartPhaseTimer(phase);

                yield return RunPhaseTasks(phase);

                retrying = _phaseRetryRequested;
                if (retrying)
                {
                    PhaseRetried?.Invoke(phase);
                    HazardDirector.Trigger(phase.EventOnRetry);
                    yield return new WaitForSeconds(1.0f);
                }
            } while (retrying);

            // Phase done inside its window — stop and hide the countdown.
            _timerDeadline = -1f;
            _timerPhase = null;
            if (_hud != null) _hud.SetTimer(-1f);
        }

        /// <summary>
        /// Arms whatever is ready, waits for something to finish, repeats.
        ///
        /// This is where "free order" lives. In a sequential phase exactly one
        /// task is ever armed, which is the behaviour every mission had before;
        /// in a FreeOrder phase all ready tasks are armed together and the loop
        /// simply reacts to whichever one the learner completes.
        /// </summary>
        IEnumerator RunPhaseTasks(MissionPhase phase)
        {
            while (!_phaseRetryRequested)
            {
                if (phase.Tasks.All(t => _completedIds.Contains(t.Id))) break;

                var ready = phase.Tasks
                    .Where(t => !_completedIds.Contains(t.Id) && !IsArmed(t) && PrerequisitesMet(t))
                    .ToList();

                if (!phase.FreeOrder)
                {
                    // One at a time, in the order the storyboard numbers them.
                    if (_armed.Count > 0 || ready.Count == 0) ready.Clear();
                    else ready.RemoveRange(1, ready.Count - 1);
                }

                foreach (var task in ready) ArmTask(task, phase);

                if (_armed.Count == 0)
                {
                    // Only reachable if AfterTaskIds names a task that cannot run.
                    Debug.LogError($"CALM_MISSION: phase '{phase.Banner}' has unfinished tasks but " +
                                   "nothing can arm — check AfterTaskIds for a cycle or a bad id.");
                    break;
                }

                RefreshArmedUi(phase);

                while (_armed.Count > 0 && !_armed.Any(r => r.Done) && !_phaseRetryRequested)
                {
                    UpdateFocus();
                    _hud.SetProgress(_focus != null ? _focus.Cond.Progress01 : -1f);
                    yield return null;
                }

                if (_phaseRetryRequested) break;

                foreach (var run in _armed.Where(r => r.Done).ToList()) FinishTask(run);
                _hud.SetProgress(-1f);
                RefreshArmedUi(phase);
                yield return new WaitForSeconds(0.7f);
            }

            // Retry, or the phase is over: take down anything still armed.
            DisarmAll();
        }

        /// <summary>
        /// Drives the phase countdown and the mission clock. Timer expiry is never
        /// a fail: it either logs a missed timer (star criterion) or gently retries
        /// the phase (Typhoon_Outdoors DURING only).
        /// </summary>
        void Update()
        {
            if (_running && _hud != null) _hud.SetClock(Time.time - _startTime);

            if (_timerDeadline < 0f || _timerPhase == null) return;
            float remaining = _timerDeadline - Time.time;
            if (_hud != null) _hud.SetTimer(Mathf.Max(0f, remaining));
            if (remaining > 0f) return;

            var phase = _timerPhase;
            _timerDeadline = -1f;
            _timerPhase = null;
            _timersMissed++;
            if (_hud != null) _hud.SetTimer(-1f);
            Debug.Log($"CALM_MISSION: phase timer expired ({phase.Banner}) — " +
                      (phase.RetryOnExpiry ? "gentle retry." : "mission continues, star criterion lost."));
            if (phase.RetryOnExpiry) _phaseRetryRequested = true;
        }

        void StartPhaseTimer(MissionPhase phase)
        {
            if (_timerPhase != null) return;
            _timerDeadline = Time.time + phase.TimerSeconds;
            _timerPhase = phase;
        }

        // ----------------------------------------------------------- task arming

        bool IsArmed(TaskDefinition task) => _armed.Any(r => r.Def.Id == task.Id);

        bool PrerequisitesMet(TaskDefinition task)
        {
            if (task.AfterTaskIds == null || task.AfterTaskIds.Length == 0) return true;
            foreach (var id in task.AfterTaskIds)
                if (!_completedIds.Contains(id)) return false;
            return true;
        }

        void ArmTask(TaskDefinition task, MissionPhase phase)
        {
            var host = new GameObject($"Task_{task.Id}");
            host.transform.SetParent(transform, false);

            var run = new TaskRun
            {
                Def = task,
                Host = host,
                Cond = AddCondition(host, task.Kind),
                Index = _indexById.TryGetValue(task.Id, out var i) ? i : 0,
            };
            run.Cond.Configure(task, _ctx);

            run.Cond.Completed += () => run.Done = true;
            run.Cond.Deviation += lineId =>
            {
                if (_mission.CountsInfractions) _infractions++;
                _hud.FlashWarning();
                if (!string.IsNullOrEmpty(lineId)) _guide.Speak(lineId, true);
                Debug.Log($"CALM_MISSION: deviation on '{task.Id}' — task stays armed.");
            };
            run.Cond.Correction += lineId =>
            {
                // Corrective line only — explicitly no infraction.
                _hud.FlashWarning();
                if (!string.IsNullOrEmpty(lineId)) _guide.Speak(lineId, true);
                Debug.Log($"CALM_MISSION: correction on '{task.Id}' (no infraction).");
            };

            if (task.RevealOnArm) SetTaskObjectsActive(task, true);
            if (task.StartsPhaseTimer && phase.TimerSeconds > 0f) StartPhaseTimer(phase);

            CacheFocusables(run);
            _armed.Add(run);
            RebuildArmedTargets();

            run.Cond.Arm();
            HazardDirector.Trigger(task.EventOnArm);
            if (task.MonitorPace) AcquirePace(task);
            if (!string.IsNullOrEmpty(task.LineId)) _guide.Speak(task.LineId);
            Debug.Log($"CALM_MISSION: task armed — {task.Id}");
            TaskStarted?.Invoke(task);
        }

        void FinishTask(TaskRun run)
        {
            _armed.Remove(run);
            run.Cond.Disarm();
            if (run.Def.MonitorPace) ReleasePace();
            RebuildArmedTargets();

            HazardDirector.Trigger(run.Def.EventOnComplete);
            if (!string.IsNullOrEmpty(run.Def.DoneLineId)) _guide.Speak(run.Def.DoneLineId);
            _completedIds.Add(run.Def.Id);
            // Recorded per task, so a learner who stops halfway still has their
            // progress counted rather than showing as never having played.
            MissionProgress.TaskCompleted(_mission.SceneName, run.Def.Id, run.Index, _completedIds.Count);

            if (_board != null)
            {
                _board.MarkChecked(run.Def.Id);
                _board.SetCount(_completedIds.Count, _mission.TotalTasks);
            }
            if (_focus == run) _focus = null;
            Destroy(run.Host);
            Debug.Log($"CALM_MISSION: task complete — {run.Def.Id}");
            TaskCompleted?.Invoke(run.Def);
        }

        void DisarmAll()
        {
            foreach (var run in _armed.ToList())
            {
                run.Cond.Disarm();
                if (run.Def.MonitorPace) ReleasePace();
                Destroy(run.Host);
            }
            _armed.Clear();
            _focus = null;
            RebuildArmedTargets();
            if (_hud != null) _hud.SetProgress(-1f);
        }

        /// <summary>
        /// Every object any armed task points at. A condition consults this before
        /// warning about a "wrong" object, so two tasks sharing a container or
        /// standing near each other cannot punish the learner for doing the other
        /// one. See MissionContext.IsClaimedElsewhere.
        /// </summary>
        void RebuildArmedTargets()
        {
            _armedTargets.Clear();
            foreach (var run in _armed)
            {
                foreach (var n in run.Def.TargetNames)
                {
                    var go = ResolveByName(n);
                    if (go != null) _armedTargets.Add(go);
                }
            }
        }

        void AcquirePace(TaskDefinition task)
        {
            if (_pace == null) _pace = gameObject.AddComponent<TeleportPaceMonitor>();
            _paceHolders++;
            _pace.Arm(_ctx.Head, task.PaceLineId ?? task.RetryLineId);
        }

        /// <summary>Ref-counted: two armed tasks can both want the pace monitor,
        /// and the first one to finish must not switch it off under the second.</summary>
        void ReleasePace()
        {
            _paceHolders = Mathf.Max(0, _paceHolders - 1);
            if (_paceHolders == 0 && _pace != null) _pace.Disarm();
        }

        // -------------------------------------------------------------- HUD focus

        void CacheFocusables(TaskRun run)
        {
            run.Focusables.Clear();
            foreach (var n in run.Def.TargetNames)
            {
                var go = ResolveByName(n);
                if (go != null) run.Focusables.Add(go.transform);
            }
            if (!string.IsNullOrEmpty(run.Def.ZoneName))
            {
                var go = ResolveByName(run.Def.ZoneName);
                if (go != null) run.Focusables.Add(go.transform);
            }
        }

        /// <summary>
        /// The HUD bar carries ONE instruction. With several tasks armed it shows
        /// whichever the learner is evidently working on: the one making progress,
        /// otherwise the nearest. Re-evaluated four times a second and biased
        /// toward the current pick, so the bar does not flicker between two jobs
        /// the learner is standing between.
        /// </summary>
        void UpdateFocus()
        {
            var live = _armed.Where(r => !r.Done).ToList();
            if (live.Count == 0) { SetFocus(null); return; }
            if (live.Count == 1) { SetFocus(live[0]); return; }
            if (_focus != null && Time.time < _focusNextEval) return;
            _focusNextEval = Time.time + 0.25f;

            TaskRun best = null;
            float bestScore = float.NegativeInfinity;
            foreach (var run in live)
            {
                // Any hold already under way beats mere proximity.
                float score = run.Cond.Progress01 > 0.01f
                    ? 1000f + run.Cond.Progress01
                    : -NearestDistance(run);
                if (run == _focus) score += 0.75f;   // stickiness, in metres
                if (score > bestScore) { bestScore = score; best = run; }
            }
            SetFocus(best);
        }

        float NearestDistance(TaskRun run)
        {
            if (run.Focusables.Count == 0 || _ctx == null || _ctx.Head == null) return 999f;
            float best = float.MaxValue;
            foreach (var t in run.Focusables)
            {
                if (t == null) continue;
                best = Mathf.Min(best, Vector3.Distance(_ctx.Head.position, t.position));
            }
            return best == float.MaxValue ? 999f : best;
        }

        void SetFocus(TaskRun run)
        {
            if (_focus == run) return;
            _focus = run;
            if (_hud == null) return;
            _hud.SetInstruction(run != null ? run.Def.Instruction : string.Empty);
            _hud.SetControlHint(run != null ? run.Def.ControlHint : string.Empty);
        }

        void RefreshArmedUi(MissionPhase phase)
        {
            var open = _armed.Where(r => !r.Done).ToList();
            if (_hud != null)
            {
                _hud.SetOrderTag(phase.FreeOrder && open.Count > 1
                    ? $"ANY ORDER  ·  {open.Count} TO DO"
                    : string.Empty);

                var done = new HashSet<int>();
                foreach (var id in _completedIds)
                    if (_indexById.TryGetValue(id, out var i)) done.Add(i);
                _hud.SetStepStates(done, new HashSet<int>(open.Select(r => r.Index)));
            }
            if (_board != null) _board.SetAvailable(open.Select(r => r.Def.Id));

            // Re-pick immediately so the bar is never blank after a completion.
            _focusNextEval = 0f;
            UpdateFocus();
        }

        /// <summary>Waits for the Guide to finish speaking, with a hard cap so a
        /// missing line id can never stall a mission.</summary>
        IEnumerator WaitForGuide(float maxSeconds)
        {
            float t = Time.time;
            while (_hud != null && _hud.SubtitleBusy && Time.time - t < maxSeconds) yield return null;
        }

        static TaskCondition AddCondition(GameObject host, TaskKind kind)
        {
            switch (kind)
            {
                case TaskKind.Gaze: return host.AddComponent<TaskGaze>();
                case TaskKind.ZoneSequence: return host.AddComponent<TaskZoneSequence>();
                case TaskKind.Zone: return host.AddComponent<TaskZone>();
                case TaskKind.Interact: return host.AddComponent<TaskInteract>();
                case TaskKind.PlaceInSocket: return host.AddComponent<TaskPlaceInSocket>();
                case TaskKind.Posture: return host.AddComponent<TaskPosture>();
                case TaskKind.HoldNearHead: return host.AddComponent<TaskHoldNearHead>();
                case TaskKind.CollectSet: return host.AddComponent<TaskCollectSet>();
                default: return host.AddComponent<TaskZone>();
            }
        }

        /// <summary>
        /// Objects for RevealOnArm tasks (crouch markers, mid-mission arrows)
        /// are placed by the content builder but must not be visible from the
        /// start. Hidden AFTER VerifySceneNames so the resolve cache already
        /// holds them (GameObject.Find cannot see inactive objects).
        /// </summary>
        void HideRevealOnArmObjects()
        {
            foreach (var task in _mission.Phases.SelectMany(p => p.Tasks))
                if (task.RevealOnArm) SetTaskObjectsActive(task, false);
        }

        void SetTaskObjectsActive(TaskDefinition task, bool active)
        {
            foreach (var n in task.TargetNames)
            {
                var go = ResolveByName(n);
                if (go != null) go.SetActive(active);
            }
            if (!string.IsNullOrEmpty(task.ZoneName))
            {
                var go = ResolveByName(task.ZoneName);
                if (go != null) go.SetActive(active);
            }
        }

        /// <summary>
        /// Authoring guard. EventOnArm fires a hazard the moment its task arms and
        /// StartsPhaseTimer starts a countdown — both are statements about WHEN,
        /// so putting them in a phase that arms everything at once means the
        /// aftershock or the clock lands at the start of the phase rather than at
        /// its intended beat. Cheap to check, and silent unless someone authors it.
        /// </summary>
        void WarnAboutFreeOrderHazards()
        {
            foreach (var phase in _mission.Phases)
            {
                if (!phase.FreeOrder || phase.Tasks.Count < 2) continue;
                foreach (var task in phase.Tasks)
                {
                    if (task.AfterTaskIds != null && task.AfterTaskIds.Length > 0) continue;
                    if (!string.IsNullOrEmpty(task.EventOnArm))
                        Debug.LogWarning($"CALM_MISSION: '{task.Id}' fires '{task.EventOnArm}' on arm inside " +
                                         $"free-order phase '{phase.Banner}' — it will fire at phase start. " +
                                         "Give it AfterTaskIds or make the phase sequential.");
                    if (task.StartsPhaseTimer)
                        Debug.LogWarning($"CALM_MISSION: '{task.Id}' starts the phase timer inside free-order " +
                                         $"phase '{phase.Banner}' — the countdown will start at phase entry.");
                }
            }
        }

        /// <summary>
        /// Hazard-side warning: infraction + HUD flash + corrective line. Used
        /// by HazardZone, FireSmokeSystem and the pace monitor, so a wrong move
        /// warns identically wherever it comes from.
        /// </summary>
        public void HazardWarn(string infractionId, string lineId)
        {
            ReportInfraction(infractionId);
            if (_hud != null) _hud.FlashWarning();
            if (_guide != null && !string.IsNullOrEmpty(lineId)) _guide.Speak(lineId, true);
        }

        // --------------------------------------------------------------- wiring

        static Transform EnsureAnchor(Transform head, string name, Vector3 localPos)
        {
            var t = head.Find(name);
            if (t == null)
            {
                var go = new GameObject(name);
                go.transform.SetParent(head, false);
                t = go.transform;
            }
            t.localPosition = localPos;
            t.localRotation = Quaternion.identity;
            return t;
        }

        static readonly Dictionary<string, GameObject> Cache = new Dictionary<string, GameObject>();

        static GameObject ResolveByName(string n)
        {
            if (string.IsNullOrEmpty(n)) return null;
            if (Cache.TryGetValue(n, out var hit) && hit != null) return hit;
            var go = GameObject.Find(n);
            if (go != null) Cache[n] = go;
            return go;
        }

        /// <summary>
        /// One consolidated error listing every scene object the definition needs
        /// but cannot find, per the implementation plan's name-based wiring rule.
        /// </summary>
        bool VerifySceneNames()
        {
            Cache.Clear();
            var missing = new List<string>();
            foreach (var task in _mission.Phases.SelectMany(p => p.Tasks))
            {
                foreach (var n in task.TargetNames)
                    if (ResolveByName(n) == null) missing.Add($"{task.Id} → {n}");
                if (!string.IsNullOrEmpty(task.ZoneName) && ResolveByName(task.ZoneName) == null)
                    missing.Add($"{task.Id} → {task.ZoneName}");
            }
            if (missing.Count == 0) return true;

            Debug.LogError("CALM_MISSION: missing scene objects — run the CALM content builder for this scene.\n  " +
                           string.Join("\n  ", missing));
            return false;
        }

        public void ReportInfraction(string id)
        {
            if (!_running || !_mission.CountsInfractions) return;
            _infractions++;
            Debug.Log($"CALM_MISSION: infraction '{id}' (total {_infractions}).");
        }
    }
}
