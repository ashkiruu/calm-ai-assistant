"""Pure context router for CALM.

Safety-critical selection is deterministic.  The learner's speech is treated only
as a question; it can never overwrite trusted VR or authenticated school state.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .mission_contract import MissionContextCheck, MissionRegistry
from .messages import FALLBACKS
from .question_scope import (
    DISASTER_TERMS,
    GENERIC_SAFETY_QUESTIONS,
    HAZARD_TERMS,
    question_hazard as _question_hazard,
    question_in_scope as _question_in_scope,
)
from .repository import ProtocolRepository
from .school_config import VALID_ROUTE_STATES, RouteResolution, SchoolProfile


SUPPORTED_LANGUAGES = {"en-PH", "fil-PH", "taglish-PH"}
CORE_REQUIRED_FIELDS = {
    "session_id",
    "scenario_id",
    "state_id",
    "hazard",
    "phase",
    "setting",
    "location_type",
    "location_zone",
    "learner_action",
    "hazard_active",
    "safe_route_id",
    "safe_zone_id",
    "responsible_adult_present",
    "timestamp",
}
ENUMS = {
    "hazard": {"fire", "earthquake", "typhoon"},
    "phase": {"before", "during", "after"},
    "setting": {"home", "school", "outdoor"},
    "location_type": {"indoors", "outdoor"},
}

EARTHQUAKE_CONDITIONAL_FIELDS = {
    "shaking_active",
    "aftershock_active",
    "approved_cover_reachable",
    "learner_heading_to_exit",
    "near_falling_or_glass_hazard",
    "structure_damaged_or_not_cleared",
    "teacher_evacuate_instruction",
    "injury_or_missing_person_known",
    "at_assembly_area",
    "headcount_active",
    "unsafe_object_visible",
    "learner_attempting_reentry",
    "injury_or_missing_person_report_pending",
}

BOOLEAN_FIELDS = {
    "hazard_active",
    "responsible_adult_present",
    "shaking_active",
    "aftershock_active",
    "approved_cover_reachable",
    "learner_heading_to_exit",
    "near_falling_or_glass_hazard",
    "unsafe_object_visible",
    "structure_damaged_or_not_cleared",
    "learner_attempting_reentry",
    "teacher_evacuate_instruction",
    "injury_or_missing_person_known",
    "injury_or_missing_person_report_pending",
    "at_assembly_area",
    "headcount_active",
}

EARTHQUAKE_REENTRY_ACTION = "attempt_reentry"

_CONDITION = re.compile(r"^([a-zA-Z0-9_]+)\s*(==|!=)\s*(.+?)$")


class ContextValidationError(ValueError):
    """Raised for a malformed assistant request outside the context envelope."""


def _parse_expected(raw: str) -> Any:
    normalized = raw.strip()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if normalized in {"null", "none"}:
        return None
    return normalized.strip("\"'")


def _location_matches(context: dict[str, Any], expected: str) -> bool:
    if expected == "indoors":
        return context.get("location_type") == "indoors"
    if expected == "outdoor":
        return context.get("location_type") == "outdoor" or context.get(
            "setting"
        ) == "outdoor"
    if expected == "home":
        return context.get("setting") == "home"
    if expected == "school":
        return context.get("setting") == "school"
    if expected == "home_or_family_shelter":
        return context.get("setting") == "home"
    return False


def _condition_matches(condition: str, context: dict[str, Any]) -> bool:
    match = _CONDITION.match(condition.strip())
    if not match:
        return False
    key, operator, raw_expected = match.groups()
    expected = _parse_expected(raw_expected)
    if key == "location":
        result = _location_matches(context, str(expected))
    elif key not in context:
        return False
    else:
        result = context[key] == expected
    return result if operator == "==" else not result


def _card_matches(card: dict[str, Any], context: dict[str, Any]) -> bool:
    applicability = card["applicability"]
    if not all(
        _condition_matches(condition, context)
        for condition in applicability.get("required_context", [])
    ):
        return False
    if any(
        _condition_matches(condition, context)
        for condition in applicability.get("excluded_context", [])
    ):
        return False
    return True


def _card_classification_matches(
    card: dict[str, Any], context: dict[str, Any]
) -> bool:
    """Prevent a precedence override from crossing hazard, phase, or setting."""

    classification = card["classification"]
    return (
        classification["hazard"] == context.get("hazard")
        and classification["phase"] == context.get("phase")
        and context.get("setting") in classification["settings"]
    )


class CALMAssistant:
    """Deterministically selects a safe protocol from trusted VR context."""

    def __init__(
        self,
        *,
        corpus_mode: str = "development",
        repository: ProtocolRepository | None = None,
        school_profile: SchoolProfile | None = None,
        school_profile_path: Path | None = None,
        mission_registry: MissionRegistry | None = None,
    ) -> None:
        self.repository = repository or ProtocolRepository(mode=corpus_mode)
        self.school = school_profile or SchoolProfile(school_profile_path)
        self.missions = mission_registry or MissionRegistry(
            protocol_ids=(card["protocol_id"] for card in self.repository.cards),
            protocol_revisions={
                card["protocol_id"]: int(card["revision"])
                for card in self.repository.cards
            },
            school_profile_id=self.school.data.get("profile_id"),
            school_profile=self.school.data,
        )

    def _validate_context(
        self,
        context: dict[str, Any],
        mission_check: MissionContextCheck | None = None,
    ) -> tuple[list[str], list[str], list[str]]:
        missing = sorted(CORE_REQUIRED_FIELDS - set(context))
        invalid: list[str] = []
        conflicts: list[str] = []
        for field, values in ENUMS.items():
            if field in context and context[field] not in values:
                invalid.append(f"{field}:INVALID_VALUE")
        for field in sorted(BOOLEAN_FIELDS & set(context)):
            if not isinstance(context[field], bool):
                invalid.append(f"{field}:NOT_BOOLEAN")
        for field in ("session_id", "scenario_id", "state_id"):
            value = context.get(field)
            if value is not None and (
                not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value)
            ):
                invalid.append(f"{field}:INVALID_IDENTIFIER")
        timestamp = context.get("timestamp")
        if timestamp is not None:
            try:
                datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                invalid.append("timestamp:INVALID_ISO8601")

        conditional_missing: list[str] = []
        if context.get("hazard") == "earthquake":
            conditional_missing = sorted(
                EARTHQUAKE_CONDITIONAL_FIELDS - set(context)
            )
            if context.get("shaking_active") is True and context.get(
                "phase"
            ) not in {"during", "after"}:
                conflicts.append("SHAKING_PHASE_CONFLICT")
            if context.get("aftershock_active") is True and context.get(
                "phase"
            ) != "after":
                conflicts.append("AFTERSHOCK_PHASE_CONFLICT")
            if context.get("aftershock_active") is True and context.get(
                "shaking_active"
            ) is not True:
                conflicts.append("AFTERSHOCK_SHAKING_CONFLICT")
            if context.get("hazard_active") is False and context.get(
                "shaking_active"
            ) is True:
                conflicts.append("HAZARD_ACTIVITY_CONFLICT")
            if (
                context.get("teacher_evacuate_instruction") is True
                and context.get("shaking_active") is True
            ):
                conflicts.append("EVACUATION_DURING_SHAKING_CONFLICT")
            if context.get("headcount_active") is True and context.get(
                "at_assembly_area"
            ) is not True:
                conflicts.append("HEADCOUNT_OUTSIDE_ASSEMBLY_CONFLICT")
            if context.get("at_assembly_area") is True:
                if context.get("location_type") != "outdoor":
                    conflicts.append("ASSEMBLY_LOCATION_TYPE_CONFLICT")
                safe_zone_id = context.get("safe_zone_id")
                if safe_zone_id and context.get("location_zone") != safe_zone_id:
                    conflicts.append("ASSEMBLY_ZONE_CONFLICT")
        route_states = context.get("route_states")
        if route_states is not None:
            if not isinstance(route_states, dict):
                invalid.append("route_states:NOT_OBJECT")
            else:
                for route_id, state in route_states.items():
                    if not isinstance(route_id, str) or not route_id:
                        invalid.append("route_states:INVALID_ROUTE_ID")
                    if state not in VALID_ROUTE_STATES:
                        invalid.append(f"route_states:{route_id}:INVALID_STATE")

        alarm_id = context.get("alarm_id")
        if alarm_id:
            alarm = self.school.alarm(alarm_id)
            if not alarm:
                conflicts.append("ALARM_ID_UNKNOWN")
            else:
                if alarm.get("hazard") not in {
                    context.get("hazard"),
                    "multi_hazard",
                }:
                    conflicts.append("ALARM_HAZARD_CONFLICT")
                if alarm.get("phase") != context.get("phase"):
                    conflicts.append("ALARM_PHASE_CONFLICT")

        mission_check = mission_check or self.missions.validate_context(context)
        if mission_check.recognized or mission_check.envelope_present:
            missing.extend(mission_check.missing)
            invalid.extend(mission_check.invalid)
            conflicts.extend(mission_check.conflicts)
        return sorted(set(missing + conditional_missing)), invalid, conflicts

    @staticmethod
    def _learner_attempting_reentry(context: dict[str, Any]) -> bool:
        """Use only trusted Unity action state to activate the re-entry guard."""

        return context.get("learner_attempting_reentry") is True or context.get(
            "learner_action"
        ) == EARTHQUAKE_REENTRY_ACTION

    def _earthquake_override(self, context: dict[str, Any]) -> str | None:
        if context.get("aftershock_active") is True:
            return "EQ-AFT-006"
        if context.get("shaking_active") is True:
            if context.get("learner_heading_to_exit") is True:
                return "EQ-DUR-003"
            if context.get("near_falling_or_glass_hazard") is True:
                return "EQ-DUR-002"
            if context.get("location_type") == "outdoor":
                return "EQ-DUR-004"
            if context.get("approved_cover_reachable") is True:
                return "EQ-DUR-001"
            return None
        if context.get("phase") == "after":
            if (
                context.get("injury_or_missing_person_known") is True
                and context.get("injury_or_missing_person_report_pending")
                is True
            ):
                return "EQ-AFT-005"
            if (
                context.get("structure_damaged_or_not_cleared") is True
                and self._learner_attempting_reentry(context)
            ):
                return "EQ-AFT-004"
            if context.get("at_assembly_area") is True:
                return "EQ-AFT-008"
            if context.get("teacher_evacuate_instruction") is True:
                return "EQ-AFT-001"
            if context.get("teacher_evacuate_instruction") is False:
                return "EQ-AFT-007"
        return None

    def _select_deterministic(
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        override_id = None
        if context.get("hazard") == "earthquake":
            override_id = self._earthquake_override(context)
            if override_id:
                card = self.repository.get(override_id)
                if card and _card_classification_matches(card, context):
                    return card, "EARTHQUAKE_STATE_PRECEDENCE"

        candidates = self.repository.candidates(
            hazard=context.get("hazard"),
            phase=context.get("phase"),
            setting=context.get("setting"),
            criticalities={"P0_CRITICAL", "P1_IMPORTANT"},
        )
        matching = [card for card in candidates if _card_matches(card, context)]
        matching.sort(
            key=lambda card: (
                -int(card["deterministic_safety"].get("priority", 0)),
                -len(card["applicability"].get("required_context", [])),
                card["protocol_id"],
            )
        )
        return (matching[0], "CARD_APPLICABILITY") if matching else (None, None)

    @staticmethod
    def _earthquake_requires_critical_protocol(context: dict[str, Any]) -> bool:
        """Prevent active earthquake states from degrading into P2 retrieval."""

        return context.get("hazard") == "earthquake" and (
            context.get("phase") == "during"
            or context.get("hazard_active") is True
            or context.get("shaking_active") is True
            or context.get("aftershock_active") is True
        )

    def _select_educational(
        self, context: dict[str, Any], question: str
    ) -> tuple[dict[str, Any] | None, bool]:
        requested_hazard = _question_hazard(question)
        cross_hazard = bool(
            requested_hazard and requested_hazard != context.get("hazard")
        )
        hazard = requested_hazard or context.get("hazard")
        candidates = self.repository.candidates(
            hazard=hazard,
            setting=context.get("setting") if not cross_hazard else None,
            criticalities={"P2_EDUCATIONAL"},
        )
        if not cross_hazard:
            contextual = [card for card in candidates if _card_matches(card, context)]
            if contextual:
                candidates = contextual
            else:
                same_phase = [
                    card
                    for card in candidates
                    if card["classification"]["phase"] == context.get("phase")
                ]
                candidates = same_phase or candidates
        ranked = self.repository.rank_educational(candidates, question)
        return (ranked[0] if ranked else None), cross_hazard

    def _runtime_route_states(self, context: dict[str, Any]) -> dict[str, str]:
        raw = context.get("route_states", {})
        states = dict(raw) if isinstance(raw, dict) else {}
        for route_id in context.get("blocked_route_ids", []) or []:
            states[str(route_id)] = "BLOCKED"
        for route_id in context.get("closed_route_ids", []) or []:
            states[str(route_id)] = "CLOSED"
        return states

    def _route_for_card(
        self, card: dict[str, Any], context: dict[str, Any]
    ) -> RouteResolution | None:
        action = card["action_code"]
        if context.get("setting") != "school" or "EVACUATE" not in action:
            return None
        return self.school.resolve_route(
            context.get("safe_route_id"),
            from_zone_id=context.get("location_zone"),
            runtime_route_states=self._runtime_route_states(context),
        )

    def _base_response(
        self,
        *,
        context: dict[str, Any],
        locale: str,
        started: float,
        mission_check: MissionContextCheck,
    ) -> dict[str, Any]:
        return {
            "session_id": context.get("session_id"),
            "scenario_id": context.get("scenario_id"),
            "state_id": context.get("state_id"),
            "protocol_id": None,
            "protocol_revision": None,
            "action_code": None,
            "criticality": None,
            "priority": None,
            "locale": locale,
            "response_text": "",
            "tts_text": "",
            "blocked_action_codes": [],
            "context_status": "valid",
            "selected_route_id": None,
            "safe_zone_id": None,
            "movement_authorized": False,
            "adult_handoff_required": True,
            "deferred_question": False,
            "decision_source": "safe_fallback",
            "selected_system_rule": None,
            "generation_mode": "DETERMINISTIC_SAFE_FALLBACK",
            "llm_used": False,
            "completion_or_error_code": "OK",
            "needs_clarification": False,
            "source_refs": [],
            "alarm": None,
            "school_config": self.school.status,
            "corpus": self.repository.status,
            "mission": mission_check.response_metadata(),
            "decision_trace": [],
            "timestamp": context.get("timestamp"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def _finalize_dashboard(self, response: dict[str, Any]) -> None:
        response["dashboard_event"] = {
            "session_id": response["session_id"],
            "scenario_id": response["scenario_id"],
            "state_id": response["state_id"],
            "protocol_id": response["protocol_id"],
            "action_code": response["action_code"],
            "completion_or_error_code": response[
                "completion_or_error_code"
            ],
            "timestamp": response["timestamp"],
            "latency_ms": response["latency_ms"],
        }

    def respond(
        self,
        *,
        question: str,
        context: dict[str, Any],
        locale: str = "en-PH",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if not isinstance(context, dict):
            raise ContextValidationError("context must be a JSON object")
        if locale not in SUPPORTED_LANGUAGES:
            raise ContextValidationError(
                f"Unsupported locale {locale!r}; use en-PH, fil-PH, or taglish-PH"
            )
        if not isinstance(question, str) or len(question) > 500:
            raise ContextValidationError("question must be a string of at most 500 characters")

        mission_check = self.missions.validate_context(context)
        response = self._base_response(
            context=context,
            locale=locale,
            started=started,
            mission_check=mission_check,
        )
        missing, invalid, conflicts = self._validate_context(
            context, mission_check
        )
        if missing or invalid:
            response.update(
                {
                    "response_text": FALLBACKS[locale]["missing"],
                    "tts_text": FALLBACKS[locale]["missing"],
                    "context_status": "missing" if missing else "invalid",
                    "completion_or_error_code": "CONTEXT_MISSING"
                    if missing
                    else "CONTEXT_INVALID",
                    "needs_clarification": True,
                    "decision_trace": [
                        *[f"missing:{field}" for field in missing],
                        *[f"invalid_or_missing_conditional:{item}" for item in invalid],
                    ],
                }
            )
            self._finalize_dashboard(response)
            return response
        if conflicts:
            response.update(
                {
                    "response_text": FALLBACKS[locale]["conflict"],
                    "tts_text": FALLBACKS[locale]["conflict"],
                    "context_status": "conflicting",
                    "completion_or_error_code": "CONTEXT_CONFLICT",
                    "needs_clarification": True,
                    "decision_trace": conflicts,
                }
            )
            self._finalize_dashboard(response)
            return response

        alarm_id = context.get("alarm_id")
        alarm = self.school.alarm(alarm_id)
        if alarm_id:
            response["alarm"] = (
                {
                    "alarm_id": alarm_id,
                    "recognized": True,
                    "meaning": alarm["meaning"],
                    "simulation_only": alarm["simulation_only"],
                }
                if alarm
                else {"alarm_id": alarm_id, "recognized": False}
            )

        card, system_rule = self._select_deterministic(context)
        in_scope = _question_in_scope(question)
        cross_hazard = False
        if not card and self._earthquake_requires_critical_protocol(context):
            response.update(
                {
                    "response_text": FALLBACKS[locale]["critical_no_protocol"],
                    "tts_text": FALLBACKS[locale]["critical_no_protocol"],
                    "completion_or_error_code": "NO_APPLICABLE_CRITICAL_PROTOCOL",
                    "needs_clarification": True,
                    "decision_trace": [
                        "active_earthquake_without_applicable_critical_protocol",
                        "educational_retrieval_blocked",
                    ],
                }
            )
            self._finalize_dashboard(response)
            return response
        if not card:
            if question.strip() and not in_scope:
                response.update(
                    {
                        "response_text": FALLBACKS[locale]["outside"],
                        "tts_text": FALLBACKS[locale]["outside"],
                        "completion_or_error_code": "OUTSIDE_DISASTER_SCOPE",
                        "decision_source": "scope_boundary",
                        "adult_handoff_required": False,
                        "decision_trace": ["question_outside_disaster_scope"],
                    }
                )
                self._finalize_dashboard(response)
                return response
            card, cross_hazard = self._select_educational(context, question)

        if not card:
            response.update(
                {
                    "response_text": FALLBACKS[locale]["no_card"],
                    "tts_text": FALLBACKS[locale]["no_card"],
                    "completion_or_error_code": "NO_APPLICABLE_APPROVED_CARD",
                    "needs_clarification": True,
                    "decision_trace": ["no_eligible_applicable_card"],
                }
            )
            self._finalize_dashboard(response)
            return response

        safety = card["deterministic_safety"]
        localized = card["language_pack"][locale]
        response_text = localized["tts_text"]
        critical = safety["criticality"] in {"P0_CRITICAL", "P1_IMPORTANT"}
        asked_hazard = _question_hazard(question)
        deferred = critical and bool(question.strip()) and (
            not in_scope
            or bool(asked_hazard and asked_hazard != context.get("hazard"))
        )
        if cross_hazard:
            response_text = FALLBACKS[locale]["general"] + response_text

        route = self._route_for_card(card, context)
        completion_code = "OK"
        needs_clarification = False
        selected_route_id = None
        safe_zone_id = context.get("safe_zone_id")
        movement_authorized = False
        route_trace: list[str] = []
        if route:
            selected_route_id = route.selected_route_id
            safe_zone_id = route.assembly_zone_id
            movement_authorized = route.movement_authorized
            route_trace.append(route.reason_code)
            if route.movement_authorized and context.get("safe_zone_id") not in {
                None,
                route.assembly_zone_id,
            }:
                movement_authorized = False
                selected_route_id = None
                safe_zone_id = None
                completion_code = "CONTEXT_CONFLICT"
                response_text = FALLBACKS[locale]["conflict"]
                route_trace.append("ROUTE_ASSEMBLY_CONFLICT")
                needs_clarification = True
            elif not route.movement_authorized:
                completion_code = "NO_APPROVED_OPEN_ROUTE"
                response_text = FALLBACKS[locale]["no_route"]
                needs_clarification = True

        source_refs = []
        for claim in card["provenance"]["source_claims"]:
            source_refs.append(
                {
                    "source_id": claim["source_id"],
                    "locator": claim["locator"],
                    "disposition": claim["disposition"],
                }
            )

        response.update(
            {
                "protocol_id": card["protocol_id"],
                "protocol_revision": card["revision"],
                "action_code": card["action_code"],
                "criticality": safety["criticality"],
                "priority": safety["priority"],
                "response_text": response_text,
                "tts_text": response_text,
                "blocked_action_codes": safety.get("blocks_action_codes", []),
                "selected_route_id": selected_route_id,
                "safe_zone_id": safe_zone_id,
                "movement_authorized": movement_authorized,
                "adult_handoff_required": bool(
                    card["approved_semantics"].get("adult_handoff")
                ),
                "deferred_question": deferred,
                "decision_source": "deterministic_router"
                if critical
                else "curated_metadata_retrieval",
                "selected_system_rule": system_rule,
                "generation_mode": safety["generation_mode"],
                "completion_or_error_code": completion_code,
                "needs_clarification": needs_clarification,
                "source_refs": source_refs,
                "decision_trace": [
                    f"trusted_state:{context['state_id']}",
                    f"selected:{card['protocol_id']}",
                    *(route_trace or []),
                    *( ["learner_question_deferred"] if deferred else [] ),
                ],
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
        if mission_check.recognized and mission_check.enforce_protocol:
            mission_mismatches: list[str] = []
            if response["protocol_id"] != mission_check.expected_protocol_id:
                mission_mismatches.append("MISSION_PROTOCOL_MISMATCH")
            if response["action_code"] != mission_check.expected_action_code:
                mission_mismatches.append("MISSION_ACTION_MISMATCH")
            if (
                response["completion_or_error_code"]
                != mission_check.expected_completion_code
            ):
                mission_mismatches.append("MISSION_COMPLETION_MISMATCH")
            if mission_mismatches:
                response.update(
                    {
                        "response_text": FALLBACKS[locale]["conflict"],
                        "tts_text": FALLBACKS[locale]["conflict"],
                        "context_status": "conflicting",
                        "completion_or_error_code": "MISSION_DECISION_MISMATCH",
                        "movement_authorized": False,
                        "selected_route_id": None,
                        "needs_clarification": True,
                        "decision_trace": [
                            *response["decision_trace"],
                            *mission_mismatches,
                        ],
                    }
                )
        self._finalize_dashboard(response)
        return response
