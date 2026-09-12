using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace CALM.Missions
{
    /// <summary>
    /// The travelling half of the objective HUD: the current instruction, the
    /// hold-progress ring, and the Guide's subtitle. A low, wide bar — deliberately
    /// small.
    ///
    /// The phase banner and checklist deliberately do NOT live here; they are on
    /// MissionBoard, fixed to a wall. A head-locked panel big enough for nine
    /// checklist rows blocks the learner's view of the room and follows them
    /// everywhere, which is exactly the thing to avoid in VR.
    ///
    /// Never Screen Space (VR rule). Builds itself in code, so there is no prefab
    /// to keep in sync and the scene stays reproducible.
    /// </summary>
    public class MissionHUD : MonoBehaviour
    {
        // Sits below the natural sightline like a dashboard, not in front of the
        // eyes. Far enough down to leave the centre of view completely clear.
        const float Distance = 1.35f;
        const float Height = -0.42f;

        Transform _head;
        TextMeshProUGUI _instruction, _hint, _learnerQuestion, _subtitle, _tag, _clock;
        Image _ring;
        Image _panel;
        RectTransform _steps;
        readonly List<Image> _pips = new List<Image>();
        float _warnUntil;

        static readonly Color PipDone = new Color(0.18f, 0.72f, 0.36f);
        static readonly Color PipCurrent = new Color(0.98f, 0.62f, 0.15f);
        static readonly Color PipPending = new Color(0.30f, 0.35f, 0.48f);

        // Opaque on purpose: at 0.88 alpha the orange frame behind bled through
        // and the panel read as plum instead of navy.
        static readonly Color Navy = new Color(0.08f, 0.13f, 0.28f, 1f);
        static readonly Color Orange = new Color(0.95f, 0.52f, 0.11f);
        static readonly Color Warn = new Color(0.72f, 0.16f, 0.13f, 0.92f);

        public static MissionHUD Create(Transform head)
        {
            var go = new GameObject("MissionHUD", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler));
            var hud = go.AddComponent<MissionHUD>();
            hud.Build(head);
            return hud;
        }

        void Build(Transform head)
        {
            _head = head;
            var canvas = GetComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            var rt = (RectTransform)transform;
            // A wide, shallow bar: ~1.1 m x 0.40 m at 1.35 m out. Rows — the
            // free-order tag, what to do, which control does it, the step dots,
            // and what the Guide just said.
            rt.sizeDelta = new Vector2(1100f, 500f);
            transform.localScale = Vector3.one * 0.0010f;

            _panel = NewImage("Panel", transform, Navy);
            Stretch(_panel.rectTransform);

            var frame = NewImage("Frame", transform, Orange);
            Stretch(frame.rectTransform, 7f);
            frame.transform.SetSiblingIndex(0);

            // Shown only in a free-order phase: "ANY ORDER - 3 TO DO". The bar can
            // only carry one instruction, so this is what tells the learner the
            // other jobs on the wall board are open too.
            _tag = NewText("OrderTag", transform, 28, Orange, TextAlignmentOptions.Center);
            Place(_tag.rectTransform, new Vector2(1000f, 34f), new Vector2(0f, 180f));
            _tag.text = string.Empty;

            // Narrower than the bar so long instructions never run under the
            // progress ring parked on the right.
            _instruction = NewText("Instruction", transform, 52, Color.white, TextAlignmentOptions.Center);
            Place(_instruction.rectTransform, new Vector2(780f, 96f), new Vector2(-50f, 116f));
            _instruction.text = string.Empty;

            // The "how" line. Orange so it reads as a separate kind of thing from
            // the white objective above it — this is the line that teaches the
            // controls, which is the entire purpose of the Tutorial mission.
            _hint = NewText("ControlHint", transform, 36, Orange, TextAlignmentOptions.Center);
            Place(_hint.rectTransform, new Vector2(1000f, 70f), new Vector2(0f, 44f));
            _hint.text = string.Empty;

            // Step dots: the learner's live "am I on track?" read-out. Deliberately
            // wordless — a filled dot per finished task is understood instantly by
            // a 9-year-old, where "Task 3 of 9" is a sentence to decode.
            _steps = new GameObject("Steps", typeof(RectTransform)).GetComponent<RectTransform>();
            _steps.SetParent(transform, false);
            Place(_steps, new Vector2(1000f, 40f), new Vector2(0f, -18f));

            _ring = NewImage("ProgressRing", transform, Orange);
            Place(_ring.rectTransform, new Vector2(112f, 112f), new Vector2(455f, 116f));
            _ring.sprite = RingSprite();
            _ring.type = Image.Type.Filled;
            _ring.fillMethod = Image.FillMethod.Radial360;
            _ring.fillOrigin = (int)Image.Origin360.Top;
            _ring.fillClockwise = true;
            _ring.fillAmount = 0f;
            _ring.gameObject.SetActive(false);

            // Keep the learner's recognized words separate from KALMA's reply.
            // Besides making the exchange readable, this lets a learner or
            // facilitator spot a speech-recognition mistake immediately.
            _learnerQuestion = NewText("LearnerQuestion", transform, 28,
                new Color(0.38f, 0.86f, 0.96f), TextAlignmentOptions.Left);
            Place(_learnerQuestion.rectTransform, new Vector2(1030f, 46f), new Vector2(0f, -76f));
            _learnerQuestion.text = string.Empty;

            // Several short teaching sentences fit here without covering the
            // mission instruction above. Long prose is still prevented by the
            // server's word cap.
            _subtitle = NewText("Subtitle", transform, 32, new Color(0.88f, 0.93f, 1f), TextAlignmentOptions.Left);
            Place(_subtitle.rectTransform, new Vector2(1030f, 138f), new Vector2(0f, -166f));
            _subtitle.text = string.Empty;

            // Phase countdown, parked opposite the ring. Hidden unless a phase
            // has a timer.
            _timer = NewText("Timer", transform, 56, new Color(1f, 0.85f, 0.4f), TextAlignmentOptions.Center);
            Place(_timer.rectTransform, new Vector2(220f, 80f), new Vector2(-455f, 116f));
            _timer.text = string.Empty;

            // Mission elapsed clock — counts UP, always visible, every mission.
            // Distinct from the phase countdown above it: this one carries no
            // pressure, it is how the facilitator sees the 5-7 min budget.
            _clock = NewText("Clock", transform, 30, new Color(0.66f, 0.74f, 0.88f), TextAlignmentOptions.Center);
            Place(_clock.rectTransform, new Vector2(220f, 40f), new Vector2(-455f, -18f));
            _clock.text = string.Empty;

            SnapInFront();
        }

        static Sprite _dotSprite;

        /// <summary>Solid circle for the step dots. Drawn in code for the same
        /// reason as the ring: builtin UI sprites are unreachable at runtime.</summary>
        static Sprite DotSprite()
        {
            if (_dotSprite != null) return _dotSprite;

            const int S = 64;
            const float R = S * 0.5f;
            var tex = new Texture2D(S, S, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            var px = new Color[S * S];
            for (int y = 0; y < S; y++)
            {
                for (int x = 0; x < S; x++)
                {
                    float dx = x - R + 0.5f, dy = y - R + 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    px[y * S + x] = new Color(1f, 1f, 1f, Mathf.Clamp01(R - d));
                }
            }
            tex.SetPixels(px);
            tex.Apply();
            _dotSprite = Sprite.Create(tex, new Rect(0, 0, S, S), new Vector2(0.5f, 0.5f));
            return _dotSprite;
        }

        static Sprite _ringSprite;

        /// <summary>
        /// Draws the ring texture in code. Unity's built-in UI skin sprites live
        /// in builtin_extra and are NOT reachable from Resources at runtime — the
        /// first attempt returned null, so the Image rendered as a solid square.
        /// </summary>
        static Sprite RingSprite()
        {
            if (_ringSprite != null) return _ringSprite;

            const int S = 128;
            const float Outer = S * 0.5f, Inner = S * 0.33f;
            var tex = new Texture2D(S, S, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            var px = new Color[S * S];
            for (int y = 0; y < S; y++)
            {
                for (int x = 0; x < S; x++)
                {
                    float dx = x - Outer + 0.5f, dy = y - Outer + 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(Outer - d) * Mathf.Clamp01(d - Inner);
                    px[y * S + x] = new Color(1f, 1f, 1f, Mathf.Clamp01(a));
                }
            }
            tex.SetPixels(px);
            tex.Apply();
            _ringSprite = Sprite.Create(tex, new Rect(0, 0, S, S), new Vector2(0.5f, 0.5f));
            return _ringSprite;
        }

        void LateUpdate()
        {
            if (_head == null) return;

            // Placed along a FLATTENED forward, not head.forward: following the
            // head's pitch drove the bar into the floor whenever the learner
            // looked down, which is precisely what they do during duck-cover-hold.
            var fwd = _head.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 0.001f) fwd = Vector3.forward;
            fwd.Normalize();

            // Crouching (task 5) leaves almost no room under the table, so pull the
            // bar in close and up to eye level instead of parking it near the floor.
            bool crouched = _head.position.y < 1.15f;
            float distance = crouched ? 0.85f : Distance;
            float height = crouched ? -0.08f : Height;

            var target = _head.position + fwd * distance + Vector3.up * height;
            transform.position = Vector3.Lerp(transform.position, target, Time.deltaTime * 3.5f);
            var look = Quaternion.LookRotation(transform.position - _head.position, Vector3.up);
            transform.rotation = Quaternion.Slerp(transform.rotation, look, Time.deltaTime * 3.5f);

            if (_panel != null)
                _panel.color = Time.time < _warnUntil ? Warn : Navy;

            DrainSubtitles();
        }

        /// <summary>
        /// One line at a time, each held long enough to actually be read, then the
        /// next. Before this, every Speak() overwrote the previous line instantly:
        /// the mission prologue was replaced by the first task's line about a
        /// second in, which is why the opening narration could not be read.
        /// </summary>
        void DrainSubtitles()
        {
            if (_subtitle == null || Time.time <= _subtitleUntil) return;

            if (_subQueue.Count > 0)
            {
                var next = _subQueue[0];
                _subQueue.RemoveAt(0);
                Present(next);
            }
            // IsNullOrEmpty, not .Length: a TextMeshProUGUI reports a null `text`
            // until something assigns it. That used to be masked because
            // MissionManager.Start spoke the prologue before the HUD's first
            // LateUpdate; the briefing panel now holds the mission for as long as
            // the learner takes to read it, so this ran null for every frame in
            // between and threw once per frame.
            else if (!string.IsNullOrEmpty(_subtitle.text))
            {
                _subtitle.text = string.Empty;
            }

            if (_learnerQuestion != null
                && Time.time > _learnerUntil
                && _subQueue.Count == 0
                && !string.IsNullOrEmpty(_learnerQuestion.text))
            {
                _learnerQuestion.text = string.Empty;
            }
        }

        void SnapInFront()
        {
            if (_head == null) return;
            var fwd = _head.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 0.001f) fwd = Vector3.forward;
            transform.position = _head.position + fwd.normalized * Distance + Vector3.up * Height;
            transform.rotation = Quaternion.LookRotation(transform.position - _head.position, Vector3.up);
        }

        // ------------------------------------------------------------ public API

        public void SetInstruction(string text) { if (_instruction != null) _instruction.text = text; }

        public void SetControlHint(string text) { if (_hint != null) _hint.text = text ?? string.Empty; }

        /// <summary>Builds one dot per task, once, at mission start.</summary>
        public void BuildSteps(int total)
        {
            if (_steps == null) return;
            foreach (Transform c in _steps) Destroy(c.gameObject);
            _pips.Clear();

            const float spacing = 38f;
            float startX = -(total - 1) * spacing * 0.5f;
            for (int i = 0; i < total; i++)
            {
                var pip = NewImage($"Step{i + 1}", _steps, PipPending);
                Place(pip.rectTransform, new Vector2(26f, 26f), new Vector2(startX + i * spacing, 0f));
                pip.sprite = DotSprite();
                _pips.Add(pip);
            }
        }

        /// <summary>
        /// Green done, orange available, grey locked. The learner can see at a
        /// glance how far they have come and how much is left — which is the whole
        /// point: reassurance that they are on the right track.
        ///
        /// A free-order phase arms several tasks at once, so "available" is a set,
        /// not a single index. The dots are keyed by the task's position in the
        /// flattened mission list, NOT by completion order, so a dot that has gone
        /// green stays green wherever it was finished.
        /// </summary>
        public void SetStepStates(HashSet<int> done, HashSet<int> available)
        {
            for (int i = 0; i < _pips.Count; i++)
            {
                bool isDone = done != null && done.Contains(i);
                bool isOpen = !isDone && available != null && available.Contains(i);
                _pips[i].color = isDone ? PipDone : (isOpen ? PipCurrent : PipPending);
                float size = isOpen ? 34f : 26f;
                _pips[i].rectTransform.sizeDelta = new Vector2(size, size);
            }
        }

        /// <summary>"ANY ORDER - 3 TO DO", or empty in a sequential phase.</summary>
        public void SetOrderTag(string text)
        {
            if (_tag != null) _tag.text = text ?? string.Empty;
        }

        /// <summary>Mission elapsed time, counting up. Negative hides it.</summary>
        public void SetClock(float seconds)
        {
            if (_clock == null) return;
            if (seconds < 0f) { _clock.text = string.Empty; return; }
            int s = Mathf.FloorToInt(seconds);
            _clock.text = $"{s / 60}:{s % 60:00}";
        }

        float _subtitleUntil;
        float _learnerUntil;
        readonly List<string> _subQueue = new List<string>();

        /// <summary>How long the queue still has to run. The mission waits on this
        /// before moving off a phase intro, instead of a hardcoded 0.6 s.</summary>
        public bool SubtitleBusy => Time.time <= _subtitleUntil || _subQueue.Count > 0;

        /// <summary>
        /// The subtitle is the Guide *speaking*, so it clears a few seconds after
        /// the line. Leaving it up permanently stacked a second copy of whatever
        /// the instruction already said, which read as a rendering bug.
        ///
        /// Lines queue rather than overwrite. <paramref name="urgent"/> is for
        /// deviation and correction lines — "Careful, glass!" has to be seen NOW
        /// and must never wait behind a completion line.
        /// </summary>
        public void ShowSubtitle(string text, bool urgent = false)
        {
            if (_subtitle == null || string.IsNullOrEmpty(text)) return;

            if (urgent)
            {
                _subQueue.Clear();
                Present(text);
                return;
            }

            if (Time.time <= _subtitleUntil)
            {
                // A deep backlog means the learner is reading history, not the
                // present. Keep the newest lines and drop the stalest.
                if (_subQueue.Count >= 3) _subQueue.RemoveAt(0);
                _subQueue.Add(text);
                return;
            }
            Present(text);
        }

        /// <summary>Show an assistant line with a stable speaker label.</summary>
        public void ShowAssistantReply(string text, bool urgent = false)
        {
            if (string.IsNullOrWhiteSpace(text)) return;
            ShowSubtitle($"KALMA  {text}", urgent);
        }

        /// <summary>
        /// Replace temporary Listening/Thinking text with one complete turn.
        /// The transcript is visible only in memory while this HUD is alive; it
        /// is never sent to Unity's Console or the persistent session report.
        /// </summary>
        public void ShowConversationTurn(string learnerText, string assistantText)
        {
            if (_learnerQuestion != null)
            {
                _learnerQuestion.text = string.IsNullOrWhiteSpace(learnerText)
                    ? string.Empty
                    : $"YOU  {learnerText}";
            }

            ShowAssistantReply(assistantText, urgent: true);
            _learnerUntil = _subtitleUntil;
        }

        void Present(string text)
        {
            _subtitle.text = text;
            // Roughly a slow reader's pace, floored so even "Good!" registers and
            // capped so a long line cannot stall the queue. These are Grade 4
            // readers — err long.
            _subtitleUntil = Time.time + Mathf.Clamp(2.5f + text.Length * 0.050f, 3f, 14f);
        }

        public void FlashWarning() => _warnUntil = Time.time + 0.9f;

        TextMeshProUGUI _timer;

        /// <summary>m:ss countdown; negative hides it. Red for the last 10 s.</summary>
        public void SetTimer(float seconds)
        {
            if (_timer == null) return;
            if (seconds < 0f) { _timer.text = string.Empty; return; }
            int s = Mathf.CeilToInt(seconds);
            _timer.text = $"{s / 60}:{s % 60:00}";
            _timer.color = seconds <= 10f ? new Color(1f, 0.35f, 0.3f) : new Color(1f, 0.85f, 0.4f);
        }

        public void SetProgress(float p01)
        {
            if (_ring == null) return;
            bool on = p01 >= 0f;
            if (_ring.gameObject.activeSelf != on) _ring.gameObject.SetActive(on);
            if (on) _ring.fillAmount = Mathf.Clamp01(p01);
        }

        public void Hide() => gameObject.SetActive(false);

        /// <summary>Brings the bar back and re-seats it in front of the learner —
        /// while hidden it stops tracking, so without the snap it would slide in
        /// from wherever it was parked.</summary>
        public void Show()
        {
            gameObject.SetActive(true);
            SnapInFront();
        }

        // -------------------------------------------------------------- helpers

        static Image NewImage(string name, Transform parent, Color c)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(CanvasRenderer), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = c;
            img.raycastTarget = false;
            return img;
        }

        static TextMeshProUGUI NewText(string name, Transform parent, float size, Color c, TextAlignmentOptions align)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            var t = go.AddComponent<TextMeshProUGUI>();
            t.fontSize = size;
            t.color = c;
            t.alignment = align;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.Normal;
            return t;
        }

        static void Place(RectTransform rt, Vector2 size, Vector2 pos)
        {
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = pos;
        }

        static void Stretch(RectTransform rt, float pad = 0f)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(-pad, -pad);
            rt.offsetMax = new Vector2(pad, pad);
        }
    }
}
