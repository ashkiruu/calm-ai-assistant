using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Networking;

namespace CALM.Assistant
{
    /// <summary>
    /// Wire format of POST /api/v1/chat. Field names are snake_case because
    /// JsonUtility matches JSON keys literally; do not rename them to C#
    /// convention without adding a converter.
    ///
    /// This mirrors the ChatResponse model in server.py. That model declares
    /// closed value sets, so the constants below cannot silently miss a case: a
    /// new branch on the server changes the OpenAPI schema and fails loudly
    /// rather than arriving unannounced in the headset.
    /// </summary>
    [Serializable]
    public class CalmAnswer
    {
        public string response_text;
        public string question;
        public string locale;
        public string task_id;
        public string scenario_id;
        public string scene;
        public string hazard;   // earthquake | fire | typhoon
        public string phase;    // before | during | after
        public string setting;  // home | school | outdoor
        public string active_simulation_instruction;
        public string mapping_status;
        public string scope_constraint;
        public bool general_qa;
        public string retrieval_mode; // task_scoped | all_supported_hazards

        public string question_scope;   // see CalmScope
        public string asked_hazard;     // empty when the learner named no hazard
        public bool deferred_question;
        public string completion_code;  // see CalmCompletion
        public string answer_source;    // llm | deterministic_fallback
        public string evidence_scope;

        public string[] retrieved_evidence_ids;
        public string[] deviation_evidence_ids;

        public string provider;
        public string model;            // empty when no model was called
        public bool llm_used;
        public string grounding_mode;
        public string prompt_policy_version;
        public CalmGeneration generation;

        // Present only on /api/v1/voice-chat.
        public string transcript;
        public string input_mode;

        /// <summary>
        /// True when a hazard is live and the learner asked about a different
        /// emergency. The answer still carries the current safety cue, so it
        /// must be shown; only the tone should differ.
        /// </summary>
        public bool IsDeferred => deferred_question;

        /// <summary>
        /// True when no model was involved. The text is reviewed wording rather
        /// than generated, and it arrives in microseconds instead of ~600ms.
        /// </summary>
        public bool IsReviewedText => answer_source == CalmSource.DeterministicFallback;
    }

    [Serializable]
    public class CalmGeneration
    {
        public int elapsed_ms;
        public int prompt_tokens;
        public int output_tokens;
        public bool output_normalized;
    }

    /// <summary>How the learner's question related to the active task.</summary>
    public static class CalmScope
    {
        public const string OnTask = "on_task";
        public const string InHazardOffTask = "in_hazard_off_task";
        public const string CrossHazard = "cross_hazard";
        public const string OutOfScope = "out_of_scope";
    }

    /// <summary>
    /// Why the answer came out the way it did. Branch on this, never on the
    /// text of the answer.
    /// </summary>
    public static class CalmCompletion
    {
        public const string Ok = "OK";
        public const string OkCrossHazard = "OK_CROSS_HAZARD";
        public const string OkInHazardOffTask = "OK_IN_HAZARD_OFF_TASK";
        public const string OkGeneralQa = "OK_GENERAL_QA";
        /// A hazard is live; the other emergency is deliberately postponed.
        public const string DeferredDuringCriticalTask = "DEFERRED_DURING_CRITICAL_TASK";
        /// In scope, but nothing curated answers it. Hand off to the teacher.
        public const string NoRelevantEvidence = "NO_RELEVANT_EVIDENCE";
        /// Not a disaster question at all.
        public const string OutsideDisasterScope = "OUTSIDE_DISASTER_SCOPE";
    }

    public static class CalmSource
    {
        public const string Llm = "llm";
        public const string DeterministicFallback = "deterministic_fallback";
    }

    public static class CalmLocale
    {
        /// Answer in whichever language the question was asked in. Request-only:
        /// a response always reports a concrete locale.
        public const string Auto = "auto";
        public const string English = "en-PH";
        public const string Filipino = "fil-PH";
        public const string Taglish = "taglish-PH";
    }

    [Serializable]
    internal class ChatRequestBody
    {
        public string question;
        public string task_id;
        public string locale;
        public string session_id;
        public string previous_question;
        public string previous_response;
    }

    [Serializable]
    internal class SpeakRequestBody
    {
        public string text;
        public string locale;
    }

    [Serializable]
    internal class ErrorResponseBody
    {
        public string detail;
    }

    /// <summary>
    /// Talks to the local CALM service. Every call is a coroutine so mission
    /// code stays on the main thread and never blocks a frame.
    ///
    /// The learner's speech is a question, never a command: nothing this client
    /// returns may change trusted mission state. Feed answers to the HUD and to
    /// audio, and let the mission framework keep owning state as it does today.
    /// </summary>
    public class CalmClient : MonoBehaviour
    {
        [Tooltip("Base URL of the local CALM service.")]
        public string BaseUrl = "http://127.0.0.1:8010";

        [Tooltip("Allow 127.0.0.1 on an Android headset only when adb reverse tcp:8010 tcp:8010 is active. Leave off for Wi-Fi/LAN builds, where loopback points at the headset rather than the teacher PC.")]
        public bool AllowAndroidLoopbackForAdbReverse = false;

        [Tooltip("Seconds before a typed question is abandoned. Warm answers take well under one second; the headroom covers a cold model load.")]
        public int RequestTimeoutSeconds = 30;

        [Tooltip("Voice adds local transcription on top of the answer, so it needs more room.")]
        public int VoiceTimeoutSeconds = 120;

        [Tooltip("Locale for answers and for the synthesis voice. \"auto\" answers in whichever language the child asked in, which is the only option that works here: the project has no language setting to read.")]
        public string Locale = CalmLocale.Auto;

        [Tooltip("Groups one session's events in the CALM log. Set by CalmAssistant per mission. Opaque and non-identifying; never derive it from anything about the learner.")]
        public string SessionId = string.Empty;

        // One previous exchange is enough to resolve "How?" and "Why?" while
        // avoiding a durable conversation history. These strings live only in
        // this component's memory and are replaced after the next answer.
        string _previousTaskId;
        string _previousQuestion;
        string _previousResponse;

        /// <summary>
        /// Ask a typed question about the task the learner is standing in.
        /// taskId must be a Unity task id from MissionLibrary; the crosswalk
        /// validator keeps both sides in step.
        /// </summary>
        public IEnumerator Ask(
            string taskId,
            string question,
            Action<CalmAnswer> onAnswer,
            Action<string> onError = null)
        {
            if (!TryValidateQuestion(taskId, question, onError)) yield break;
            if (!TryGetServiceUrl("/api/v1/chat", out string url, onError)) yield break;

            var body = new ChatRequestBody
            {
                question = question,
                task_id = taskId,
                locale = Locale,
                session_id = SessionId,
            };
            AddConversationContext(taskId, body);
            byte[] payload = Encoding.UTF8.GetBytes(JsonUtility.ToJson(body));

            using (var request = new UnityWebRequest(url, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(payload);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = RequestTimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    onError?.Invoke(DescribeFailure(request));
                    yield break;
                }

                CalmAnswer answer = null;
                string parseError = null;
                try
                {
                    answer = JsonUtility.FromJson<CalmAnswer>(request.downloadHandler.text);
                }
                catch (Exception error)
                {
                    parseError = error.Message;
                }

                if (!IsValidAnswer(answer, taskId, out string validationError))
                {
                    string reason = !string.IsNullOrEmpty(parseError) ? parseError : validationError;
                    onError?.Invoke($"Could not read the CALM answer: {reason}");
                    yield break;
                }
                RememberTurn(answer);
                onAnswer?.Invoke(answer);
            }
        }

        /// <summary>
        /// Send recorded speech. The clip is transcribed on this machine and the
        /// temporary file is deleted; learner audio never leaves the device.
        /// </summary>
        public IEnumerator AskByVoice(
            string taskId,
            byte[] audio,
            Action<CalmAnswer> onAnswer,
            Action<string> onError = null,
            string fileName = "question.wav",
            string contentType = "audio/wav")
        {
            if (string.IsNullOrWhiteSpace(taskId))
            {
                onError?.Invoke("No active CALM task is available for this question.");
                yield break;
            }
            if (audio == null || audio.Length <= 44)
            {
                onError?.Invoke("The recording was empty. Hold the button while you ask.");
                yield break;
            }
            if (!TryGetServiceUrl("/api/v1/voice-chat", out string url, onError)) yield break;

            var form = new WWWForm();
            form.AddBinaryData("audio_file", audio, fileName, contentType);
            form.AddField("task_id", taskId);
            form.AddField("locale", Locale);
            if (!string.IsNullOrEmpty(SessionId)) form.AddField("session_id", SessionId);
            if (HasConversationContext(taskId))
            {
                form.AddField("previous_question", _previousQuestion);
                form.AddField("previous_response", _previousResponse);
            }

            using (var request = UnityWebRequest.Post(url, form))
            {
                request.timeout = VoiceTimeoutSeconds;
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    onError?.Invoke(DescribeFailure(request));
                    yield break;
                }

                CalmAnswer answer = null;
                string parseError = null;
                try
                {
                    answer = JsonUtility.FromJson<CalmAnswer>(request.downloadHandler.text);
                }
                catch (Exception error)
                {
                    parseError = error.Message;
                }

                if (!IsValidAnswer(answer, taskId, out string validationError))
                {
                    string reason = !string.IsNullOrEmpty(parseError) ? parseError : validationError;
                    onError?.Invoke($"Could not read the CALM answer: {reason}");
                    yield break;
                }
                RememberTurn(answer);
                onAnswer?.Invoke(answer);
            }
        }

        bool HasConversationContext(string taskId)
        {
            return taskId == _previousTaskId
                && !string.IsNullOrWhiteSpace(_previousQuestion)
                && !string.IsNullOrWhiteSpace(_previousResponse);
        }

        void AddConversationContext(string taskId, ChatRequestBody body)
        {
            if (!HasConversationContext(taskId)) return;
            body.previous_question = _previousQuestion;
            body.previous_response = _previousResponse;
        }

        void RememberTurn(CalmAnswer answer)
        {
            if (answer == null || string.IsNullOrWhiteSpace(answer.task_id)) return;
            _previousTaskId = answer.task_id;
            _previousQuestion = answer.question;
            _previousResponse = answer.response_text;
        }

        public void ResetConversation()
        {
            _previousTaskId = null;
            _previousQuestion = null;
            _previousResponse = null;
        }

        /// <summary>
        /// Fetch spoken audio for a sentence CALM already produced.
        ///
        /// Synthesis is the one step that leaves the machine, so it is the one
        /// step that fails on a school network. That failure is not worth
        /// interrupting a lesson for: show the subtitle and carry on.
        /// </summary>
        public IEnumerator Speak(
            string text,
            string locale,
            Action<AudioClip> onClip,
            Action<string> onUnavailable = null)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                onUnavailable?.Invoke("There is no assistant text to speak.");
                yield break;
            }
            if (!TryGetServiceUrl("/api/v1/speak", out string url, onUnavailable)) yield break;

            // Synthesis needs a concrete voice. "auto" is meaningful only for
            // an answer, where the question itself carries the language, so a
            // caller should pass the locale the answer came back in.
            var body = new SpeakRequestBody
            {
                text = text,
                locale = string.IsNullOrEmpty(locale) ? CalmLocale.English : locale,
            };
            byte[] payload = Encoding.UTF8.GetBytes(JsonUtility.ToJson(body));

            using (var request = new UnityWebRequest(url, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(payload);
                var handler = new DownloadHandlerAudioClip(string.Empty, AudioType.MPEG);
                request.downloadHandler = handler;
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = RequestTimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    onUnavailable?.Invoke(DescribeFailure(request));
                    yield break;
                }
                onClip?.Invoke(handler.audioClip);
            }
        }

        /// <summary>
        /// Fetch the task ids CALM has curated evidence for.
        ///
        /// Unity has more tasks than CALM covers: the tutorial steps teach
        /// controls rather than hazard protocol, so no protocol card maps to
        /// them. Asking about one is a 404, and a headset that discovers this
        /// per task fills the log with errors that look like a broken service.
        /// Knowing the set up front turns that into silence, which is the
        /// correct behaviour during a tutorial.
        /// </summary>
        public IEnumerator FetchKnownTaskIds(
            Action<HashSet<string>> onResult,
            Action<string> onError = null)
        {
            if (!TryGetServiceUrl("/api/v1/unity/tasks", out string url, onError)) yield break;
            using (var request = UnityWebRequest.Get(url))
            {
                request.timeout = RequestTimeoutSeconds;
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    onError?.Invoke(DescribeFailure(request));
                    yield break;
                }

                // JsonUtility cannot read a bare nested array of objects here,
                // and pulling in a JSON library for one field is not worth it.
                var ids = new HashSet<string>();
                foreach (Match match in TaskIdPattern.Matches(request.downloadHandler.text))
                {
                    ids.Add(match.Groups[1].Value);
                }
                if (ids.Count == 0)
                {
                    onError?.Invoke("The CALM task list was empty or unreadable.");
                    yield break;
                }
                onResult?.Invoke(ids);
            }
        }

        static readonly Regex TaskIdPattern = new Regex("\"task_id\"\\s*:\\s*\"([^\"]+)\"");

        /// <summary>Check the service is up before a session starts.</summary>
        public IEnumerator CheckHealth(Action<bool> onResult)
        {
            if (!TryGetServiceUrl("/health", out string url, _ => onResult?.Invoke(false))) yield break;
            using (var request = UnityWebRequest.Get(url))
            {
                request.timeout = 10;
                yield return request.SendWebRequest();
                onResult?.Invoke(request.result == UnityWebRequest.Result.Success);
            }
        }

        /// <summary>
        /// Turn a transport failure into something a teacher could act on. The
        /// common case in a classroom is that the CALM service is not running.
        /// </summary>
        static string DescribeFailure(UnityWebRequest request)
        {
            if (request.result == UnityWebRequest.Result.ConnectionError)
            {
                return "Cannot reach the CALM service. Check that it is running.";
            }
            if (request.responseCode == 404)
            {
                return "That task id is not in the CALM crosswalk.";
            }
            if (request.responseCode == 503)
            {
                return DetailOr(request, "The CALM service is temporarily unavailable.");
            }
            if (request.responseCode == 413 || request.responseCode == 422)
                return DetailOr(request, "The question could not be accepted.");
            return $"CALM request failed ({request.responseCode}): {request.error}";
        }

        bool TryValidateQuestion(string taskId, string question, Action<string> onError)
        {
            if (string.IsNullOrWhiteSpace(taskId))
            {
                onError?.Invoke("No active CALM task is available for this question.");
                return false;
            }
            if (string.IsNullOrWhiteSpace(question))
            {
                onError?.Invoke("Ask KALMA a short question first.");
                return false;
            }
            if (question.Trim().Length > 500)
            {
                onError?.Invoke("That question is too long. Please ask it in one short sentence.");
                return false;
            }
            return true;
        }

        bool TryGetServiceUrl(string path, out string url, Action<string> onError)
        {
            url = null;
            string root = (BaseUrl ?? string.Empty).Trim().TrimEnd('/');
            if (!Uri.TryCreate(root, UriKind.Absolute, out Uri parsed)
                || (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps))
            {
                onError?.Invoke("CALM Base Url must be a complete http:// or https:// address.");
                return false;
            }

#if UNITY_ANDROID && !UNITY_EDITOR
            bool loopback = parsed.IsLoopback || parsed.Host == "0.0.0.0";
            if (loopback && !AllowAndroidLoopbackForAdbReverse)
            {
                onError?.Invoke(
                    "This headset is configured for 127.0.0.1, which points at the headset. "
                    + "Use the teacher PC's LAN address, or enable Android loopback only after adb reverse tcp:8010 tcp:8010.");
                return false;
            }
#endif

            url = root + path;
            return true;
        }

        static bool IsValidAnswer(CalmAnswer answer, string expectedTaskId, out string reason)
        {
            if (answer == null)
            {
                reason = "the response was empty";
                return false;
            }
            if (string.IsNullOrWhiteSpace(answer.response_text))
            {
                reason = "response_text was missing";
                return false;
            }
            if (string.IsNullOrWhiteSpace(answer.task_id) || answer.task_id != expectedTaskId)
            {
                reason = "the response did not match the active task";
                return false;
            }
            if (string.IsNullOrWhiteSpace(answer.locale))
            {
                reason = "locale was missing";
                return false;
            }
            reason = null;
            return true;
        }

        static string DetailOr(UnityWebRequest request, string fallback)
        {
            try
            {
                string json = request.downloadHandler != null ? request.downloadHandler.text : null;
                var body = !string.IsNullOrWhiteSpace(json)
                    ? JsonUtility.FromJson<ErrorResponseBody>(json)
                    : null;
                return !string.IsNullOrWhiteSpace(body?.detail) ? body.detail : fallback;
            }
            catch
            {
                return fallback;
            }
        }
    }
}
