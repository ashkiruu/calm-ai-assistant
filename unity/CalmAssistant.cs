using System.Collections;
using System.Collections.Generic;
using System.Linq;
using CALM.Missions;
using UnityEngine;

namespace CALM.Assistant
{
    /// <summary>
    /// Grounds KALMA in the active mission task, presents answers, and owns the
    /// assistant's voice/UI state. It never completes tasks or changes mission
    /// state: MissionManager remains the only simulation authority.
    /// </summary>
    [RequireComponent(typeof(CalmClient))]
    public class CalmAssistant : MonoBehaviour
    {
        [Tooltip("Mission manager whose task changes drive the assistant.")]
        public MissionManager Manager;

        [Tooltip("HUD that shows the learner's words and KALMA's answer.")]
        public MissionHUD Hud;

        [Tooltip("Plays the spoken answer when synthesis is available.")]
        public AudioSource Voice;

        [Tooltip("Speak answers aloud as well as showing them.")]
        public bool SpeakAloud = true;

        [Tooltip("Asked on the learner's behalf when a task begins.")]
        public string OpeningQuestion = "What should I do now?";

        [Tooltip("Delay automatic guidance so it does not talk over the mission cue.")]
        public float OpeningDelaySeconds = 1.5f;

        [Tooltip("Volume multiplier for other scene audio while KALMA speaks.")]
        [Range(0.1f, 1f)]
        public float AmbientDuckFactor = 0.38f;

        CalmClient _client;
        HashSet<string> _knownTasks;
        Coroutine _pending;
        Coroutine _presentation;
        Coroutine _referenceBinding;
        Coroutine _taskLoading;
        Coroutine _stateReset;
        bool _managerSubscribed;
        string _queuedTaskId;
        string _prewarmTaskId;
        CalmAnswer _prewarmedAnswer;
        bool _prewarmInFlight;
        AudioSource _earconSource;
        AudioClip _listenEarcon;
        AudioClip _respondEarcon;
        AudioClip _errorEarcon;
        AudioClip _ownedVoiceClip;
        readonly Dictionary<AudioSource, float> _duckedSources = new Dictionary<AudioSource, float>();

        public bool TasksReady => _knownTasks != null;

        void Awake()
        {
            _client = GetComponent<CalmClient>();
            _client.SessionId = $"unity-{System.Guid.NewGuid():N}".Substring(0, 20);
            if (Manager == null)
                Manager = FindFirstObjectByType<MissionManager>(FindObjectsInactive.Include);
            EnsureAudioSources();
        }

        void OnEnable()
        {
            SubscribeManager();
            _referenceBinding = StartCoroutine(BindRuntimeReferences());
            _taskLoading = StartCoroutine(LoadKnownTasksWithRetry());
            SetIndicator(KalmaVisualState.Idle);
        }

        void OnDisable()
        {
            UnsubscribeManager();
            StopTrackedCoroutines();
            StopVoiceAndRestoreMix();
            DestroyOwnedVoiceClip();
            SetIndicator(KalmaVisualState.Idle);
        }

        void OnDestroy()
        {
            DestroyClip(_listenEarcon);
            DestroyClip(_respondEarcon);
            DestroyClip(_errorEarcon);
        }

        IEnumerator BindRuntimeReferences()
        {
            while (enabled && (Manager == null || Hud == null || Camera.main == null))
            {
                if (Manager == null)
                    Manager = FindFirstObjectByType<MissionManager>(FindObjectsInactive.Include);
                SubscribeManager();

                if (Hud == null)
                    Hud = FindFirstObjectByType<MissionHUD>(FindObjectsInactive.Include);

                BindPushToTalk();
                AttachVoiceToCamera();
                yield return null;
            }

            BindPushToTalk();
            AttachVoiceToCamera();
            _referenceBinding = null;
        }

        void SubscribeManager()
        {
            if (_managerSubscribed || Manager == null) return;
            Manager.BriefingStarted += OnBriefingStarted;
            Manager.TaskStarted += OnTaskStarted;
            _managerSubscribed = true;
        }

        void UnsubscribeManager()
        {
            if (!_managerSubscribed || Manager == null) return;
            Manager.BriefingStarted -= OnBriefingStarted;
            Manager.TaskStarted -= OnTaskStarted;
            _managerSubscribed = false;
        }

        void BindPushToTalk()
        {
            var pushToTalk = GetComponent<CalmPushToTalk>();
            if (pushToTalk == null) return;
            pushToTalk.Client = _client;
            pushToTalk.Manager = Manager;
            pushToTalk.Hud = Hud;
        }

        IEnumerator LoadKnownTasksWithRetry()
        {
            float wait = 1f;
            while (enabled && _knownTasks == null)
            {
                HashSet<string> loaded = null;
                string failure = null;
                yield return _client.FetchKnownTaskIds(
                    ids => loaded = ids,
                    error => failure = error);

                if (loaded != null && loaded.Count > 0)
                {
                    _knownTasks = loaded;
                    _taskLoading = null;
                    TryStartPrewarm();

                    string queued = _queuedTaskId;
                    _queuedTaskId = null;
                    if (!string.IsNullOrEmpty(queued) && IsStillCurrent(queued))
                        ScheduleGuide(queued);
                    yield break;
                }

                Debug.LogWarning($"[CALM] Task list unavailable; retrying in {wait:F0}s. {failure}");
                yield return new WaitForSecondsRealtime(wait);
                wait = Mathf.Min(wait * 2f, 10f);
            }
            _taskLoading = null;
        }

        void OnBriefingStarted(MissionDefinition mission)
        {
            _prewarmTaskId = mission?.Phases?
                .SelectMany(phase => phase.Tasks)
                .FirstOrDefault(task => task != null && !string.IsNullOrEmpty(task.Id))?.Id;
            TryStartPrewarm();
        }

        void TryStartPrewarm()
        {
            if (_prewarmInFlight || _prewarmedAnswer != null || _knownTasks == null
                || string.IsNullOrEmpty(_prewarmTaskId) || !_knownTasks.Contains(_prewarmTaskId))
                return;
            StartCoroutine(Prewarm(_prewarmTaskId));
        }

        IEnumerator Prewarm(string taskId)
        {
            _prewarmInFlight = true;
            yield return _client.Ask(
                taskId,
                OpeningQuestion,
                answer =>
                {
                    if (_prewarmTaskId == taskId) _prewarmedAnswer = answer;
                },
                error => Debug.LogWarning($"[CALM] First answer could not be warmed: {error}"));
            _prewarmInFlight = false;
        }

        void OnTaskStarted(TaskDefinition task)
        {
            if (task == null || string.IsNullOrEmpty(task.Id)) return;
            _client.ResetConversation();

            if (_knownTasks == null)
            {
                // The service may have started after Unity. Preserve the first
                // cue and replay it once the authoritative task list arrives.
                _queuedTaskId = task.Id;
                return;
            }
            if (!_knownTasks.Contains(task.Id)) return;
            ScheduleGuide(task.Id);
        }

        void ScheduleGuide(string taskId)
        {
            CancelAutomaticGuidance();
            _pending = StartCoroutine(Guide(taskId));
        }

        IEnumerator Guide(string taskId)
        {
            yield return new WaitForSeconds(OpeningDelaySeconds);
            if (!IsStillCurrent(taskId))
            {
                _pending = null;
                yield break;
            }

            if (_prewarmTaskId == taskId && _prewarmInFlight)
            {
                float deadline = Time.realtimeSinceStartup + _client.RequestTimeoutSeconds + 2f;
                while (_prewarmInFlight && Time.realtimeSinceStartup < deadline && IsStillCurrent(taskId))
                    yield return null;
            }

            if (_prewarmTaskId == taskId && _prewarmedAnswer != null)
            {
                CalmAnswer cached = _prewarmedAnswer;
                _prewarmedAnswer = null;
                _pending = null;
                StartPresentation(taskId, cached, false);
                yield break;
            }

            SetIndicator(KalmaVisualState.Thinking);
            CalmAnswer answer = null;
            string failure = null;
            yield return _client.Ask(taskId, OpeningQuestion, value => answer = value, error => failure = error);
            _pending = null;

            if (answer != null && IsStillCurrent(taskId))
                StartPresentation(taskId, answer, false);
            else if (!string.IsNullOrEmpty(failure))
            {
                Debug.LogWarning($"[CALM] {failure}");
                NotifyError(failure, showOnHud: false);
            }
        }

        public bool CanAskTask(string taskId)
        {
            return !string.IsNullOrEmpty(taskId)
                && _knownTasks != null
                && _knownTasks.Contains(taskId);
        }

        /// <summary>Give the learner's live question priority over an automatic cue.</summary>
        public void BeginLearnerQuestion()
        {
            CancelAutomaticGuidance();
            if (_presentation != null)
            {
                StopCoroutine(_presentation);
                _presentation = null;
            }
            StopVoiceAndRestoreMix();
            DestroyOwnedVoiceClip();
        }

        public void CancelAutomaticGuidance()
        {
            if (_pending == null) return;
            StopCoroutine(_pending);
            _pending = null;
        }

        public void NotifyListening()
        {
            SetIndicator(KalmaVisualState.Listening);
            PlayEarcon(_listenEarcon);
        }

        public void NotifyThinking() => SetIndicator(KalmaVisualState.Thinking);

        public void NotifyError(string message, bool showOnHud = true)
        {
            SetIndicator(KalmaVisualState.Error);
            PlayEarcon(_errorEarcon);
            if (showOnHud && Hud != null && !string.IsNullOrWhiteSpace(message))
                Hud.ShowAssistantReply(message, urgent: true);
            if (_stateReset != null) StopCoroutine(_stateReset);
            _stateReset = StartCoroutine(ResetIndicatorAfter(1.8f));
        }

        IEnumerator ResetIndicatorAfter(float seconds)
        {
            yield return new WaitForSecondsRealtime(seconds);
            SetIndicator(KalmaVisualState.Idle);
            _stateReset = null;
        }

        public void PresentAnswer(string taskId, CalmAnswer answer)
        {
            if (answer == null || !IsStillCurrent(taskId)) return;
            StartPresentation(taskId, answer, true);
        }

        void StartPresentation(string taskId, CalmAnswer answer, bool showLearnerQuestion)
        {
            if (_presentation != null) StopCoroutine(_presentation);
            _presentation = StartCoroutine(Present(taskId, answer, showLearnerQuestion));
        }

        IEnumerator Present(string taskId, CalmAnswer answer, bool showLearnerQuestion)
        {
            if (!IsStillCurrent(taskId))
            {
                _presentation = null;
                yield break;
            }

            if (Hud != null)
            {
                if (showLearnerQuestion)
                {
                    string heard = !string.IsNullOrWhiteSpace(answer.transcript)
                        ? answer.transcript
                        : answer.question;
                    Hud.ShowConversationTurn(heard, answer.response_text);
                }
                else
                {
                    Hud.ShowAssistantReply(answer.response_text, answer.IsDeferred);
                }
            }

            if (!SpeakAloud || Voice == null)
            {
                SetIndicator(KalmaVisualState.Idle);
                _presentation = null;
                yield break;
            }

            AudioClip clip = null;
            string synthesisFailure = null;
            SetIndicator(KalmaVisualState.Thinking);
            yield return _client.Speak(
                answer.response_text,
                answer.locale,
                value => clip = value,
                reason => synthesisFailure = reason);

            if (clip == null || !IsStillCurrent(taskId))
            {
                if (!string.IsNullOrEmpty(synthesisFailure))
                    Debug.Log($"[CALM] Voice unavailable: {synthesisFailure}");
                DestroyClip(clip);
                SetIndicator(KalmaVisualState.Idle);
                _presentation = null;
                yield break;
            }

            DestroyOwnedVoiceClip();
            _ownedVoiceClip = clip;
            Voice.clip = clip;
            DuckAmbientAudio();
            PlayEarcon(_respondEarcon);
            SetIndicator(KalmaVisualState.Speaking);
            Voice.Play();
            while (Voice.isPlaying && IsStillCurrent(taskId)) yield return null;

            if (Voice.isPlaying) Voice.Stop();
            RestoreAmbientAudio();
            DestroyOwnedVoiceClip();
            SetIndicator(KalmaVisualState.Idle);
            _presentation = null;
        }

        public void AskAboutCurrentTask(string question)
        {
            var task = Manager != null ? Manager.ActiveTask : null;
            if (task == null || !CanAskTask(task.Id)) return;
            BeginLearnerQuestion();
            _pending = StartCoroutine(AskTyped(task.Id, question));
        }

        IEnumerator AskTyped(string taskId, string question)
        {
            SetIndicator(KalmaVisualState.Thinking);
            CalmAnswer answer = null;
            string failure = null;
            yield return _client.Ask(taskId, question, value => answer = value, error => failure = error);
            _pending = null;
            if (answer != null) StartPresentation(taskId, answer, true);
            else if (!string.IsNullOrEmpty(failure)) NotifyError(failure);
        }

        bool IsStillCurrent(string taskId)
        {
            return Manager != null
                && Manager.ActiveTask != null
                && Manager.ActiveTask.Id == taskId;
        }

        void EnsureAudioSources()
        {
            if (Voice == null) Voice = GetComponent<AudioSource>();
            if (Voice == null) Voice = gameObject.AddComponent<AudioSource>();
            Voice.playOnAwake = false;
            Voice.loop = false;
            Voice.spatialBlend = 0.35f;
            Voice.minDistance = 0.2f;
            Voice.maxDistance = 4f;

            var earcon = transform.Find("KALMA Earcons");
            if (earcon == null)
            {
                var go = new GameObject("KALMA Earcons");
                go.transform.SetParent(transform, false);
                earcon = go.transform;
            }
            _earconSource = earcon.GetComponent<AudioSource>();
            if (_earconSource == null) _earconSource = earcon.gameObject.AddComponent<AudioSource>();
            _earconSource.playOnAwake = false;
            _earconSource.spatialBlend = 0.2f;
            _earconSource.volume = 0.26f;

            _listenEarcon = CreateEarcon("KALMA Listen", 660f, 880f, 0.11f);
            _respondEarcon = CreateEarcon("KALMA Respond", 520f, 740f, 0.14f);
            _errorEarcon = CreateEarcon("KALMA Error", 360f, 280f, 0.16f);
        }

        void AttachVoiceToCamera()
        {
            var camera = Camera.main;
            if (camera == null) return;
            if (transform.parent != camera.transform)
                transform.SetParent(camera.transform, false);
            transform.localPosition = new Vector3(0.36f, -0.20f, 0.80f);
            transform.localRotation = Quaternion.identity;
        }

        void PlayEarcon(AudioClip clip)
        {
            if (_earconSource != null && clip != null) _earconSource.PlayOneShot(clip);
        }

        void SetIndicator(KalmaVisualState state)
        {
            if (AIAssistantHUD.Current != null) AIAssistantHUD.Current.SetState(state);
        }

        void DuckAmbientAudio()
        {
            RestoreAmbientAudio();
            foreach (var source in FindObjectsByType<AudioSource>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                if (source == null || source == Voice || source == _earconSource || !source.isPlaying) continue;
                _duckedSources[source] = source.volume;
                source.volume *= AmbientDuckFactor;
            }
        }

        void RestoreAmbientAudio()
        {
            foreach (var pair in _duckedSources)
                if (pair.Key != null) pair.Key.volume = pair.Value;
            _duckedSources.Clear();
        }

        void StopVoiceAndRestoreMix()
        {
            if (Voice != null && Voice.isPlaying) Voice.Stop();
            RestoreAmbientAudio();
        }

        void DestroyOwnedVoiceClip()
        {
            if (_ownedVoiceClip == null) return;
            if (Voice != null && Voice.clip == _ownedVoiceClip) Voice.clip = null;
            DestroyClip(_ownedVoiceClip);
            _ownedVoiceClip = null;
        }

        void StopTrackedCoroutines()
        {
            if (_pending != null) StopCoroutine(_pending);
            if (_presentation != null) StopCoroutine(_presentation);
            if (_referenceBinding != null) StopCoroutine(_referenceBinding);
            if (_taskLoading != null) StopCoroutine(_taskLoading);
            if (_stateReset != null) StopCoroutine(_stateReset);
            _pending = _presentation = _referenceBinding = _taskLoading = _stateReset = null;
        }

        static AudioClip CreateEarcon(string name, float startHz, float endHz, float seconds)
        {
            const int sampleRate = 22050;
            int count = Mathf.CeilToInt(sampleRate * seconds);
            var data = new float[count];
            float phase = 0f;
            for (int i = 0; i < count; i++)
            {
                float t = i / (float)Mathf.Max(1, count - 1);
                float frequency = Mathf.Lerp(startHz, endHz, t);
                phase += 2f * Mathf.PI * frequency / sampleRate;
                float envelope = Mathf.Sin(Mathf.PI * t);
                data[i] = Mathf.Sin(phase) * envelope * 0.32f;
            }
            var clip = AudioClip.Create(name, count, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static void DestroyClip(AudioClip clip)
        {
            if (clip != null) Object.Destroy(clip);
        }
    }
}
