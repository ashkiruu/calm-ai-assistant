using System.Collections;
using CALM.Missions;
using UnityEngine;
using UnityEngine.InputSystem;
#if UNITY_ANDROID && !UNITY_EDITOR
using UnityEngine.Android;
#endif

namespace CALM.Assistant
{
    /// <summary>
    /// Privacy-preserving push-to-talk: audio is captured only while the
    /// learner holds V or a controller secondary button, then sent to the
    /// local CALM service and released from memory.
    /// </summary>
    [RequireComponent(typeof(CalmAssistant))]
    public class CalmPushToTalk : MonoBehaviour
    {
        public CalmClient Client;
        public MissionManager Manager;
        public MissionHUD Hud;

        [Tooltip("Maximum recording duration before capture is stopped automatically.")]
        public int MaxSeconds = 15;

        [Tooltip("Whisper's native speech-analysis rate.")]
        public int SampleRate = 16000;

        [Tooltip("Reject room noise below this peak instead of letting the transcriber invent speech.")]
        [Range(0f, 0.2f)]
        public float SilenceThreshold = 0.01f;

        [Tooltip("Shortest hold treated as a question rather than an accidental tap.")]
        public float MinSeconds = 0.4f;

        [Tooltip("Logs verbatim child speech to Player.log. Keep off outside supervised debugging.")]
        public bool VerboseTranscripts = false;

        CalmAssistant _assistant;
        InputAction _talkAction;
        Coroutine _sendRoutine;
        string _device;
        AudioClip _clip;
        float _startedAt;
        bool _recording;
        bool _sending;

        void Awake()
        {
            _assistant = GetComponent<CalmAssistant>();
            if (Client == null) Client = GetComponent<CalmClient>();
            if (Manager == null)
                Manager = FindFirstObjectByType<MissionManager>(FindObjectsInactive.Include);
        }

        void OnEnable()
        {
            _talkAction = new InputAction("CalmPushToTalk", InputActionType.Button);
            _talkAction.AddBinding("<XRController>{LeftHand}/secondaryButton");
            _talkAction.AddBinding("<XRController>{RightHand}/secondaryButton");
            _talkAction.AddBinding("<Keyboard>/v");
            _talkAction.started += OnPressed;
            _talkAction.canceled += OnReleased;
            _talkAction.Enable();
        }

        void OnDisable()
        {
            if (_talkAction != null)
            {
                _talkAction.started -= OnPressed;
                _talkAction.canceled -= OnReleased;
                _talkAction.Disable();
                _talkAction.Dispose();
                _talkAction = null;
            }
            if (_sendRoutine != null) StopCoroutine(_sendRoutine);
            _sendRoutine = null;
            _sending = false;
            StopRecording();
            ReleaseRecording();
        }

        void Update()
        {
            if (_recording && Time.unscaledTime - _startedAt >= MaxSeconds)
                Finish();
        }

        void OnPressed(InputAction.CallbackContext context)
        {
            if (_recording || _sending) return;
            string taskId = CurrentTaskId();
            if (taskId == null) return;

            if (!_assistant.CanAskTask(taskId))
            {
                if (!_assistant.TasksReady)
                    _assistant.NotifyError("KALMA is connecting. Try again in a moment.");
                return;
            }

#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Microphone))
            {
                Permission.RequestUserPermission(Permission.Microphone);
                _assistant.NotifyError("Allow microphone access, then hold the talk button again.");
                return;
            }
#endif

            if (Microphone.devices == null || Microphone.devices.Length == 0)
            {
                _assistant.NotifyError("No microphone is available.");
                return;
            }

            _assistant.BeginLearnerQuestion();
            _device = Microphone.devices[0];
            _clip = Microphone.Start(_device, false, Mathf.Max(1, MaxSeconds), Mathf.Max(8000, SampleRate));
            if (_clip == null)
            {
                _device = null;
                _assistant.NotifyError("The microphone could not start. Check its permission and try again.");
                return;
            }

            _startedAt = Time.unscaledTime;
            _recording = true;
            _assistant.NotifyListening();
            if (Hud != null) Hud.ShowAssistantReply("Listening…", urgent: true);
        }

        void OnReleased(InputAction.CallbackContext context)
        {
            if (_recording) Finish();
        }

        void Finish()
        {
            int samples = !string.IsNullOrEmpty(_device) ? Microphone.GetPosition(_device) : 0;
            float held = Time.unscaledTime - _startedAt;
            StopRecording();

            if (_clip == null) return;
            if (held < MinSeconds || samples <= 0)
            {
                ReleaseRecording();
                _assistant.NotifyError("Hold the button while you ask.");
                return;
            }

            if (CalmWav.PeakLevel(_clip, samples) < SilenceThreshold)
            {
                ReleaseRecording();
                _assistant.NotifyError("I did not hear anything. Try again.");
                return;
            }

            byte[] wav = CalmWav.Encode(_clip, samples);
            ReleaseRecording();
            _sendRoutine = StartCoroutine(Send(wav));
        }

        void StopRecording()
        {
            if (_recording && !string.IsNullOrEmpty(_device)) Microphone.End(_device);
            _recording = false;
            _device = null;
        }

        void ReleaseRecording()
        {
            if (_clip == null) return;
            Destroy(_clip);
            _clip = null;
        }

        IEnumerator Send(byte[] wav)
        {
            string taskId = CurrentTaskId();
            if (taskId == null || Client == null)
            {
                _sendRoutine = null;
                yield break;
            }

            _sending = true;
            _assistant.NotifyThinking();
            if (Hud != null) Hud.ShowAssistantReply("Thinking…", urgent: true);

            CalmAnswer answer = null;
            string failure = null;
            yield return Client.AskByVoice(
                taskId,
                wav,
                value => answer = value,
                error => failure = error);

            _sending = false;
            _sendRoutine = null;
            if (answer != null)
            {
                LogHeard(answer.transcript);
                _assistant.PresentAnswer(taskId, answer);
            }
            else if (!string.IsNullOrEmpty(failure))
            {
                Debug.LogWarning($"[CALM] {failure}");
                _assistant.NotifyError(failure);
            }
        }

        void LogHeard(string transcript)
        {
            if (VerboseTranscripts)
            {
                Debug.Log($"[CALM] heard: {transcript}");
                return;
            }
            int words = string.IsNullOrWhiteSpace(transcript)
                ? 0
                : transcript.Split(' ').Length;
            Debug.Log($"[CALM] heard {words} word(s).");
        }

        string CurrentTaskId()
        {
            if (Manager == null)
                Manager = FindFirstObjectByType<MissionManager>(FindObjectsInactive.Include);
            var task = Manager != null ? Manager.ActiveTask : null;
            return task != null && !string.IsNullOrEmpty(task.Id) ? task.Id : null;
        }
    }
}
