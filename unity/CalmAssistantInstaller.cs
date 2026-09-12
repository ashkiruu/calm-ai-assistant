using System.Linq;
using CALM.Assistant;
using CALM.Missions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Adds the CALM assistant to a mission scene and wires its references. Run
/// from the "CALM" menu.
///
/// Doing this by hand across nine hazard scenes invites the one mistake that is
/// hard to see: a reference left empty, which fails silently at runtime rather
/// than at build time. The installer finds the mission manager and HUD already
/// in the scene and connects them.
/// </summary>
public static class CalmAssistantInstaller
{
    const string RootName = "CALM Assistant";

    /// <summary>
    /// Wire the open scene. Marks it dirty and never saves, so reviewing and
    /// saving stays a deliberate act.
    /// </summary>
    [MenuItem("CALM/Assistant/Add To Open Scene")]
    public static void AddToOpenScene()
    {
        var scene = SceneManager.GetActiveScene();
        if (!scene.IsValid())
        {
            Debug.LogWarning("[CALM] No scene is open.");
            return;
        }
        if (Install(scene))
        {
            EditorSceneManager.MarkSceneDirty(scene);
            Debug.Log($"[CALM] Assistant ready in {scene.name}. Save the scene to keep it.");
        }
    }

    [MenuItem("CALM/Assistant/Add To All Mission Scenes")]
    public static void AddToAllMissionScenes()
    {
        // Only scenes backed by an authoritative MissionLibrary definition.
        // A hazard-named environment may be a placeholder or exploration scene
        // (Fire_Outdoors currently is); filename prefixes alone are not enough.
        var paths = AssetDatabase
            .FindAssets("t:Scene", new[] { "Assets/Scenes" })
            .Select(AssetDatabase.GUIDToAssetPath)
            .Where(IsMissionScene)
            .OrderBy(path => path)
            .ToList();

        if (paths.Count == 0)
        {
            Debug.LogWarning("[CALM] No mission scenes found under Assets/Scenes.");
            return;
        }

        foreach (var path in paths)
        {
            var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
            if (Install(scene))
            {
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                Debug.Log($"[CALM] Assistant installed in {scene.name}.");
            }
        }
        Debug.Log($"[CALM] Finished {paths.Count} mission scenes.");
    }

    static bool IsMissionScene(string path)
    {
        var name = System.IO.Path.GetFileNameWithoutExtension(path);
        return MissionLibrary.GetMission(name) != null;
    }

    static bool Install(Scene scene)
    {
        var manager = FindInScene<MissionManager>(scene);
        if (manager == null)
        {
            // Without a mission manager there are no task changes to react to,
            // so an assistant here would be inert. Say so rather than leaving a
            // half-wired object behind.
            Debug.LogWarning($"[CALM] {scene.name} has no MissionManager; skipped.");
            return false;
        }

        var root = scene.GetRootGameObjects()
            .FirstOrDefault(item => item.name == RootName);
        if (root == null)
        {
            root = new GameObject(RootName);
            SceneManager.MoveGameObjectToScene(root, scene);
            Undo.RegisterCreatedObjectUndo(root, "Add CALM Assistant");
        }

        var client = GetOrAdd<CalmClient>(root);
        var assistant = GetOrAdd<CalmAssistant>(root);
        var voice = GetOrAdd<AudioSource>(root);

        // Partly spatial: anchored near KALMA so the voice has a gentle source
        // without becoming hard to hear when the learner turns their head.
        voice.playOnAwake = false;
        voice.loop = false;
        voice.spatialBlend = 0.35f;
        voice.minDistance = 0.2f;
        voice.maxDistance = 4f;

        var talk = GetOrAdd<CalmPushToTalk>(root);

        var hud = FindInScene<MissionHUD>(scene);
        assistant.Manager = manager;
        assistant.Hud = hud;
        assistant.Voice = voice;

        talk.Client = client;
        talk.Manager = manager;
        talk.Hud = hud;

        if (hud == null)
        {
            Debug.LogWarning(
                $"[CALM] {scene.name} has no MissionHUD; answers will be spoken "
                + "but not shown. Assign Hud by hand if one is added later.");
        }

        EditorUtility.SetDirty(client);
        EditorUtility.SetDirty(assistant);
        EditorUtility.SetDirty(talk);
        EditorUtility.SetDirty(voice);
        return true;
    }

    /// <summary>
    /// Unity objects use overloaded null semantics. Avoid the C# ?? operator:
    /// a missing native component can survive that check as a "fake null" and
    /// then throw MissingComponentException when a property is accessed.
    /// </summary>
    static T GetOrAdd<T>(GameObject root) where T : Component
    {
        var component = root.GetComponent<T>();
        return component != null ? component : Undo.AddComponent<T>(root);
    }

    /// <summary>
    /// Find a component in one scene, including on inactive objects.
    ///
    /// The general find helpers skip inactive objects, and a HUD that starts
    /// hidden is exactly the case here.
    /// </summary>
    static T FindInScene<T>(Scene scene) where T : Component
    {
        return scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<T>(true))
            .FirstOrDefault();
    }
}
