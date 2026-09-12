using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>The visible communication state of KALMA.</summary>
public enum KalmaVisualState
{
    Idle,
    Listening,
    Thinking,
    Speaking,
    Error,
}

/// <summary>
/// Head-locked, display-only KALMA indicator. It stays in the lower-right
/// periphery at a comfortable focal distance and never takes raycast focus.
/// The avatar is procedural so every mission can use the approved KALMA shape
/// without depending on a large concept-art texture.
/// </summary>
public class AIAssistantHUD : MonoBehaviour
{
    // Intentionally not serialized. Legacy scenes carried per-instance values
    // that put the assistant over briefing text. A viewport anchor is stable
    // across aspect ratios and XR camera projection settings.
    static readonly Vector3 ComfortableViewportPoint = new Vector3(0.86f, 0.22f, 0.85f);

    static readonly Color Navy = new Color(0.035f, 0.065f, 0.13f, 1f);
    static readonly Color Cyan = new Color(0.35f, 0.88f, 1f, 1f);
    static readonly Color Green = new Color(0.35f, 0.95f, 0.58f, 1f);
    static readonly Color Amber = new Color(1f, 0.72f, 0.25f, 1f);
    static readonly Color Red = new Color(1f, 0.30f, 0.28f, 1f);

    static Sprite _kalmaSprite;
    readonly List<Image> _waveBars = new List<Image>();
    Image _icon;
    Image _background;
    Vector3 _restScale;
    KalmaVisualState _state;

    public static AIAssistantHUD Current { get; private set; }
    public KalmaVisualState State => _state;

    void Awake()
    {
        Current = this;
        _icon = FindImage("Icon");
        _background = FindImage("Background");

        if (_icon != null)
        {
            _icon.sprite = CreateKalmaSprite();
            _icon.preserveAspect = true;
            _icon.raycastTarget = false;
        }
        if (_background != null) _background.raycastTarget = false;

        BuildWaveform();
        _restScale = transform.localScale;
        SetState(KalmaVisualState.Idle);
    }

    void Start()
    {
        var cam = Camera.main;
        if (cam == null)
        {
            Debug.LogWarning("[AIAssistantHUD] No Main Camera found; HUD not attached.");
            return;
        }

        if (transform.parent != cam.transform)
            transform.SetParent(cam.transform, false);

        transform.position = cam.ViewportToWorldPoint(ComfortableViewportPoint);
        transform.rotation = cam.transform.rotation;
        _restScale = transform.localScale;

        var canvas = GetComponent<Canvas>();
        if (canvas != null) canvas.worldCamera = cam;
    }

    void OnDestroy()
    {
        if (Current == this) Current = null;
    }

    public void SetState(KalmaVisualState state)
    {
        _state = state;
        Color accent = AccentFor(state);
        if (_background != null)
            _background.color = new Color(accent.r, accent.g, accent.b, state == KalmaVisualState.Idle ? 0.18f : 0.34f);

        bool showWave = state == KalmaVisualState.Listening || state == KalmaVisualState.Speaking;
        foreach (var bar in _waveBars)
        {
            bar.gameObject.SetActive(showWave);
            bar.color = accent;
        }
    }

    void Update()
    {
        Color accent = AccentFor(_state);
        float speed = _state == KalmaVisualState.Listening ? 5.5f : 3.8f;
        bool active = _state != KalmaVisualState.Idle;
        float pulse = active ? 1f + 0.035f * (0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * speed)) : 1f;
        transform.localScale = _restScale * pulse;

        if (_icon != null)
        {
            float tint = active ? 0.08f + 0.06f * Mathf.Sin(Time.unscaledTime * speed) : 0f;
            _icon.color = Color.Lerp(Color.white, accent, Mathf.Max(0f, tint));
        }

        if (_state == KalmaVisualState.Listening || _state == KalmaVisualState.Speaking)
        {
            for (int i = 0; i < _waveBars.Count; i++)
            {
                float height = 12f + 18f * (0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * speed + i * 1.7f));
                _waveBars[i].rectTransform.sizeDelta = new Vector2(7f, height);
            }
        }
    }

    Image FindImage(string childName)
    {
        var child = transform.Find(childName);
        return child != null ? child.GetComponent<Image>() : null;
    }

    void BuildWaveform()
    {
        for (int i = 0; i < 3; i++)
        {
            var go = new GameObject($"Wave {i + 1}", typeof(RectTransform), typeof(CanvasRenderer), typeof(Image));
            go.transform.SetParent(transform, false);
            var rect = (RectTransform)go.transform;
            rect.anchorMin = rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.anchoredPosition = new Vector2(56f + i * 11f, -42f);
            rect.sizeDelta = new Vector2(7f, 16f);
            var bar = go.GetComponent<Image>();
            bar.raycastTarget = false;
            _waveBars.Add(bar);
        }
    }

    static Color AccentFor(KalmaVisualState state)
    {
        switch (state)
        {
            case KalmaVisualState.Listening: return Cyan;
            case KalmaVisualState.Thinking: return Amber;
            case KalmaVisualState.Speaking: return Green;
            case KalmaVisualState.Error: return Red;
            default: return Cyan;
        }
    }

    static Sprite CreateKalmaSprite()
    {
        if (_kalmaSprite != null) return _kalmaSprite;

        const int width = 160;
        const int height = 120;
        var texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
        texture.name = "KALMA Procedural Avatar";
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;

        var pixels = new Color32[width * height];
        Color32 clear = new Color32(0, 0, 0, 0);
        Color32 shell = new Color32(224, 218, 205, 255);
        Color32 face = new Color32(13, 25, 48, 255);
        Color32 eye = new Color32(120, 235, 255, 255);

        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                float nx = (x - width * 0.5f) / (width * 0.48f);
                float ny = (y - height * 0.5f) / (height * 0.44f);
                float outer = nx * nx + ny * ny;
                Color32 color = clear;
                if (outer <= 1f) color = shell;

                float fx = (x - width * 0.5f) / (width * 0.37f);
                float fy = (y - height * 0.54f) / (height * 0.30f);
                if (fx * fx + fy * fy <= 1f) color = face;

                bool leftEye = Sqr(x - 62f) + Sqr(y - 66f) <= 7f * 7f;
                bool rightEye = Sqr(x - 98f) + Sqr(y - 66f) <= 7f * 7f;
                if (leftEye || rightEye) color = eye;

                // The cyan seam on KALMA's lower-left shell is the persistent
                // identity cue; state colour lives in the surrounding halo.
                float inner = Mathf.Pow((x - 75f) / 70f, 2f) + Mathf.Pow((y - 57f) / 49f, 2f);
                if (outer <= 1f && inner > 0.93f && inner < 1.04f && x < 104 && y < 55)
                    color = eye;

                pixels[y * width + x] = color;
            }
        }

        texture.SetPixels32(pixels);
        texture.Apply(false, true);
        _kalmaSprite = Sprite.Create(texture, new Rect(0, 0, width, height), new Vector2(0.5f, 0.5f), 100f);
        _kalmaSprite.name = "KALMA Procedural Avatar";
        return _kalmaSprite;
    }

    static float Sqr(float value) => value * value;
}
