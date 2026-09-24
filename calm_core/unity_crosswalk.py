"""Validated bridge between Unity mission tasks and curated RAG evidence."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CROSSWALK = ROOT / "config" / "unity_scenario_crosswalk.v1.json"
DEFAULT_CARDS = ROOT / "corpus" / "protocol_cards.jsonl"

HAZARDS = {"earthquake", "fire", "typhoon"}
SETTINGS = {"home", "school", "outdoor"}
PHASES = {"before", "during", "after"}
BLOCKED_LIFECYCLE_STATES = {
    "DRAFT",
    "NEEDS_CURRENT_SOURCE",
    "CONFLICT_HOLD",
    "SUSPENDED",
    "SUPERSEDED",
    "RETIRED",
}
# The Tutorial contains many learner-training tasks that do not use the
# backend assistant. Reconcile the one Tutorial task that actually calls CALM
# without claiming every tutorial TEACH/TRY beat is a backend task.
UNITY_TASK_PATTERN = re.compile(
    r'\bId\s*=\s*"((?:eq_home_[bda]\d+_[A-Za-z0-9_]+|(?:eq|fire|typ)_(?:home|sch|out)_\d+_[A-Za-z0-9_]+|tut_13_ask))"'
)

# Task-id drift between this repo and the Unity project. These two prefixes are
# the ONLY errors CALM_UNITY_DRIFT=warn is allowed to downgrade, so a genuine
# schema or corpus fault can never be waved through by the dev escape hatch.
DRIFT_ERROR_PREFIXES = (
    "Unity tasks missing from crosswalk: ",
    "Crosswalk tasks absent from Unity: ",
)
# Env var name, and the one value that relaxes startup. Anything else (unset
# included) keeps the check fatal.
DRIFT_ENV_VAR = "CALM_UNITY_DRIFT"
DRIFT_WARN = "warn"


class UnknownTaskError(KeyError):
    """Unity asked about a task id the crosswalk does not carry.

    A subclass of KeyError so existing callers keep working, but a distinct type
    so the API can tell it apart from *any other* KeyError raised anywhere in the
    pipeline. `/api/v1/chat` mapped a bare KeyError to HTTP 404 "unknown task
    id"; a corpus defect -- a card missing a language_pack locale, say -- would
    therefore have been reported to Unity as a bad task id, sending whoever
    debugged it to the crosswalk to look for something that was never wrong.
    """


class CrosswalkValidationError(RuntimeError):
    """Raised when the Unity-to-corpus mapping is not safe to load."""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise CrosswalkValidationError(f"{path} must contain a JSON object")
    return value


def _read_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or not value.get("protocol_id"):
                raise CrosswalkValidationError(
                    f"{path.name}:{line_number} is not a protocol card"
                )
            protocol_id = value["protocol_id"]
            if protocol_id in cards:
                raise CrosswalkValidationError(
                    f"Duplicate protocol_id in {path.name}: {protocol_id}"
                )
            cards[protocol_id] = value
    return cards


def _configured_unity_path(data: dict[str, Any]) -> Path | None:
    unity = data.get("unity_source", {})
    project_root = unity.get("project_root")
    library = unity.get("mission_library")
    if not project_root or not library:
        return None
    return Path(project_root) / Path(library)


def validate_crosswalk(
    crosswalk_path: Path | None = None,
    cards_path: Path | None = None,
    unity_library_path: Path | None = None,
) -> dict[str, Any]:
    """Validate schema, corpus references, and optional live Unity task coverage."""

    crosswalk_path = crosswalk_path or DEFAULT_CROSSWALK
    cards_path = cards_path or DEFAULT_CARDS
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = _read_json(crosswalk_path)
        cards = _read_cards(cards_path)
    except (OSError, json.JSONDecodeError, CrosswalkValidationError) as exc:
        return {"status": "FAIL", "errors": [str(exc)], "warnings": []}

    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if data.get("context_contract_version") != "1.2":
        errors.append("context_contract_version must be 1.2")

    generation = data.get("generation_contract", {})
    if generation.get("scenario_instruction_field") != "active_simulation_instruction":
        errors.append("generation contract has the wrong scenario instruction field")
    if generation.get("safety_evidence_field") != "retrieved_safety_evidence":
        errors.append("generation contract has the wrong safety evidence field")
    if generation.get("raw_storyboard_is_safety_evidence") is not False:
        errors.append("raw Unity storyboard text must not be marked as safety evidence")
    if generation.get("raw_pdf_retrieval_allowed") is not False:
        errors.append("raw PDF retrieval must remain disabled")

    allowed_statuses = set(data.get("allowed_mapping_statuses", []))
    expected_statuses = {"ready", "local_review", "evidence_gap", "scenario_bound"}
    if allowed_statuses != expected_statuses:
        errors.append("allowed_mapping_statuses does not match the v1 status set")

    missions = data.get("missions")
    if not isinstance(missions, list) or not missions:
        errors.append("missions must be a non-empty list")
        missions = []

    scene_ids: set[str] = set()
    scenario_ids: set[str] = set()
    task_ids: set[str] = set()
    protocol_refs: set[str] = set()
    hazard_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for mission in missions:
        if not isinstance(mission, dict):
            errors.append("every mission must be an object")
            continue
        scene = mission.get("scene")
        scenario_id = mission.get("scenario_id")
        hazard = mission.get("hazard")
        setting = mission.get("setting")
        tasks = mission.get("tasks")

        if not isinstance(scene, str) or not scene:
            errors.append("mission is missing scene")
            scene = "<missing-scene>"
        elif scene in scene_ids:
            errors.append(f"duplicate scene: {scene}")
        scene_ids.add(scene)

        if not isinstance(scenario_id, str) or not scenario_id:
            errors.append(f"{scene}: missing scenario_id")
        elif scenario_id in scenario_ids:
            errors.append(f"duplicate scenario_id: {scenario_id}")
        scenario_ids.add(str(scenario_id))

        if hazard not in HAZARDS:
            errors.append(f"{scene}: invalid hazard {hazard!r}")
        else:
            hazard_counts[hazard] += 1
        if setting not in SETTINGS:
            errors.append(f"{scene}: invalid setting {setting!r}")
        if not isinstance(tasks, list):
            errors.append(f"{scene}: tasks must be a list")
            continue
        if mission.get("implemented_task_count") != len(tasks):
            errors.append(
                f"{scene}: implemented_task_count does not equal {len(tasks)}"
            )

        for task in tasks:
            if not isinstance(task, dict):
                errors.append(f"{scene}: task must be an object")
                continue
            task_id = task.get("task_id")
            label = f"{scene}/{task_id or '<missing-task-id>'}"
            if not isinstance(task_id, str) or not task_id:
                errors.append(f"{label}: missing task_id")
            elif task_id in task_ids:
                errors.append(f"duplicate task_id: {task_id}")
            task_ids.add(str(task_id))

            general_qa = task.get("general_qa", False)
            if not isinstance(general_qa, bool):
                errors.append(f"{label}: general_qa must be a boolean")
            elif general_qa and not task.get("scope_constraint"):
                errors.append(f"{label}: general_qa task needs a scope_constraint")

            phase = task.get("phase")
            status = task.get("mapping_status")
            # A Home mission can leave the house. The park/garden tasks use
            # outdoor protocol cards while earlier tasks remain home-scoped.
            task_setting = task.get("setting", setting)
            if phase not in PHASES:
                errors.append(f"{label}: invalid phase {phase!r}")
            if task_setting not in SETTINGS:
                errors.append(f"{label}: invalid setting {task_setting!r}")
            if status not in allowed_statuses:
                errors.append(f"{label}: invalid mapping_status {status!r}")
            else:
                status_counts[status] += 1
            for field in (
                "learner_action",
                "active_simulation_instruction",
                "required_trusted_flags",
            ):
                if not task.get(field):
                    errors.append(f"{label}: missing {field}")
            if status in {"scenario_bound", "evidence_gap"} and not task.get(
                "scope_constraint"
            ):
                errors.append(f"{label}: {status} task needs a scope_constraint")
            practice_steps = task.get("practice_steps", [])
            if practice_steps and (
                not isinstance(practice_steps, list)
                or any(not isinstance(step, str) or not step.strip() for step in practice_steps)
            ):
                errors.append(f"{label}: practice_steps must contain non-empty strings")

            primary_ids = task.get("protocol_ids")
            # A storyboard-declared evidence gap cannot name a card that does
            # not exist. It remains explicit and needs a scope_constraint.
            if not isinstance(primary_ids, list) or (
                not primary_ids and status != "evidence_gap"
            ):
                errors.append(f"{label}: protocol_ids must be a non-empty list unless evidence_gap")
                primary_ids = []
            referenced_ids = primary_ids + task.get("deviation_protocol_ids", [])
            for protocol_id in referenced_ids:
                protocol_refs.add(protocol_id)
                card = cards.get(protocol_id)
                if card is None:
                    errors.append(f"{label}: unknown protocol_id {protocol_id}")
                    continue
                classification = card.get("classification", {})
                if classification.get("hazard") != hazard and not general_qa:
                    errors.append(f"{label}: {protocol_id} has the wrong hazard")
                if task_setting not in classification.get("settings", []) and not general_qa:
                    errors.append(f"{label}: {protocol_id} does not apply to {task_setting}")
                if (
                    classification.get("phase") != phase
                    and not task.get("allow_cross_phase_grounding", False)
                    and not general_qa
                ):
                    errors.append(
                        f"{label}: {protocol_id} is cross-phase without explicit permission"
                    )
                lifecycle = card.get("review", {}).get("lifecycle_state")
                if lifecycle in BLOCKED_LIFECYCLE_STATES:
                    errors.append(
                        f"{label}: {protocol_id} has blocked lifecycle {lifecycle}"
                    )

    live_unity_path = unity_library_path
    if live_unity_path is None:
        # During an isolated Unity worktree build, validate against that branch
        # without rewriting the configured live project_root in the crosswalk.
        override = os.environ.get("CALM_UNITY_LIBRARY_OVERRIDE")
        if override:
            live_unity_path = Path(override)
        else:
            configured_path = _configured_unity_path(data)
            if configured_path and configured_path.exists():
                live_unity_path = configured_path
            elif configured_path:
                warnings.append(f"Unity mission library not found: {configured_path}")

    if live_unity_path is not None:
        try:
            unity_text = live_unity_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"cannot read Unity mission library: {exc}")
        else:
            unity_task_ids = set(UNITY_TASK_PATTERN.findall(unity_text))
            missing_from_config = sorted(unity_task_ids - task_ids)
            stale_config_ids = sorted(task_ids - unity_task_ids)
            if missing_from_config:
                errors.append(
                    DRIFT_ERROR_PREFIXES[0] + ", ".join(missing_from_config)
                )
            if stale_config_ids:
                errors.append(
                    DRIFT_ERROR_PREFIXES[1] + ", ".join(stale_config_ids)
                )

        unity_root = live_unity_path.parents[3] if len(live_unity_path.parents) > 3 else None
        if unity_root:
            for mission in missions:
                storyboard = mission.get("storyboard")
                if storyboard and not (unity_root / Path(storyboard)).exists():
                    errors.append(f"missing Unity storyboard: {storyboard}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "crosswalk_version": data.get("crosswalk_version"),
        "mission_count": len(missions),
        "task_count": len(task_ids),
        "hazard_mission_counts": dict(sorted(hazard_counts.items())),
        "mapping_status_counts": dict(sorted(status_counts.items())),
        "referenced_protocol_count": len(protocol_refs),
        "unity_library_checked": str(live_unity_path) if live_unity_path else None,
        "errors": errors,
        "warnings": warnings,
    }


class UnityScenarioCrosswalk:
    """Read-only task lookup used to build context-aware RAG requests."""

    def __init__(
        self,
        crosswalk_path: Path | None = None,
        cards_path: Path | None = None,
    ) -> None:
        self.crosswalk_path = crosswalk_path or DEFAULT_CROSSWALK
        self.cards_path = cards_path or DEFAULT_CARDS
        report = validate_crosswalk(
            self.crosswalk_path,
            self.cards_path,
            unity_library_path=None,
        )
        # Validation always runs at full strength; only the RAISE is negotiable.
        # A dev machine that has the Unity project checked out gets a hard stop
        # on task-id drift, because a task Unity does not know about is a task
        # whose push-to-talk silently no-ops in the headset. Set
        # CALM_UNITY_DRIFT=warn for one process to boot anyway while the two
        # sides are being reconciled -- the drift is then reported on every
        # startup rather than forgotten.
        self.unity_drift: list[str] = [
            error
            for error in report["errors"]
            if error.startswith(DRIFT_ERROR_PREFIXES)
        ]
        if report["status"] != "PASS":
            blocking = [error for error in report["errors"] if error not in self.unity_drift]
            relaxed = os.environ.get(DRIFT_ENV_VAR, "").strip().lower() == DRIFT_WARN
            if blocking or not relaxed:
                raise CrosswalkValidationError("; ".join(report["errors"]))
            print(
                f"WARNING [{DRIFT_ENV_VAR}={DRIFT_WARN}] Unity task drift tolerated: "
                + "; ".join(self.unity_drift),
                file=sys.stderr,
            )

        self.data = _read_json(self.crosswalk_path)
        self.cards = _read_cards(self.cards_path)
        self._by_task_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for mission in self.data["missions"]:
            for task in mission["tasks"]:
                self._by_task_id[task["task_id"]] = (mission, task)

    @property
    def task_count(self) -> int:
        return len(self._by_task_id)

    @property
    def mission_count(self) -> int:
        return len(self.data["missions"])

    @property
    def task_ids(self) -> tuple[str, ...]:
        """Stable full registry for clients, validators, and audit harnesses."""

        return tuple(sorted(self._by_task_id))

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        found = self._by_task_id.get(task_id)
        if found is None:
            return None
        mission, task = found
        return {
            "scene": mission["scene"],
            "scenario_id": mission["scenario_id"],
            "hazard": mission["hazard"],
            "setting": mission["setting"],
            "location_type": mission["location_type"],
            **task,
        }

    def retrieval_plan(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            raise UnknownTaskError(f"Unknown Unity task_id: {task_id}")
        evidence_ids = task["protocol_ids"]
        return {
            "task_id": task_id,
            "scenario_id": task["scenario_id"],
            "scene": task["scene"],
            "active_simulation_instruction": task[
                "active_simulation_instruction"
            ],
            "retrieved_safety_evidence": [self.cards[item] for item in evidence_ids],
            "deviation_safety_evidence": [
                self.cards[item] for item in task.get("deviation_protocol_ids", [])
            ],
            "retrieval_filters": {
                "hazard": task["hazard"],
                "phase": task["phase"],
                "setting": task["setting"],
            },
            "general_qa": bool(task.get("general_qa", False)),
            "retrieval_mode": (
                "all_supported_hazards"
                if task.get("general_qa", False)
                else "task_scoped"
            ),
            "required_trusted_flags": task["required_trusted_flags"],
            "mapping_status": task["mapping_status"],
            "scope_constraint": task.get("scope_constraint"),
            "practice_steps": task.get("practice_steps", []),
        }
