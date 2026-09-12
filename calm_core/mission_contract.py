"""Versioned, executable VR mission contracts for CALM.

The mission contract does not let CALM control the VR story.  Unity remains the
trusted scenario authority.  CALM uses the contract to reject unknown states,
state/context mismatches, and transitions that are not part of the reviewed
learning mission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MISSIONS_DIR = ROOT / "config" / "missions"

STATE_KINDS = {"main", "correction", "safe_hold", "terminal"}
MISSION_METADATA_FIELDS = {
    "mission_revision",
    "state_seq",
    "previous_state_seq",
    "previous_state_id",
    "transition_event",
}
TRANSITION_KINDS = {
    "progression",
    "correction",
    "correction_return",
    "safe_hold",
    "safe_hold_return",
}


class MissionContractError(RuntimeError):
    """Raised when a mission definition is unsafe or internally inconsistent."""


@dataclass(frozen=True)
class MissionContextCheck:
    recognized: bool
    envelope_present: bool = False
    mission_id: str | None = None
    mission_revision: str | None = None
    state_id: str | None = None
    state_label: str | None = None
    state_kind: str | None = None
    expected_protocol_id: str | None = None
    expected_action_code: str | None = None
    expected_completion_code: str | None = None
    enforce_protocol: bool = False
    simulation_only: bool = False
    terminal: bool = False
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    allowed_transitions: tuple[dict[str, str], ...] = ()
    dependency_status: str | None = None

    @property
    def valid(self) -> bool:
        return not (self.missing or self.invalid or self.conflicts)

    def response_metadata(self) -> dict[str, Any]:
        if not self.recognized:
            return {
                "recognized": False,
                "envelope_present": self.envelope_present,
                "mission_id": self.mission_id,
                "state_id": self.state_id,
                "contract_status": (
                    "rejected" if self.envelope_present else "not_applicable"
                ),
            }
        return {
            "recognized": True,
            "envelope_present": self.envelope_present,
            "mission_id": self.mission_id,
            "mission_revision": self.mission_revision,
            "state_id": self.state_id,
            "state_label": self.state_label,
            "state_kind": self.state_kind,
            "expected_protocol_id": self.expected_protocol_id,
            "expected_action_code": self.expected_action_code,
            "expected_completion_code": self.expected_completion_code,
            "simulation_only": self.simulation_only,
            "terminal": self.terminal,
            "dependency_status": self.dependency_status,
            "contract_status": "valid" if self.valid else "rejected",
            "allowed_transitions": [dict(item) for item in self.allowed_transitions],
        }


class MissionContract:
    """A validated mission graph plus strict expanded-context checks."""

    def __init__(
        self,
        path: Path,
        *,
        protocol_ids: Iterable[str] | None = None,
        protocol_revisions: dict[str, int] | None = None,
        school_profile_id: str | None = None,
        school_profile: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        try:
            with path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise MissionContractError(f"Cannot load mission {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise MissionContractError(f"{path} must contain a JSON object")
        self.data: dict[str, Any] = data
        self.mission_id = str(data.get("mission_id", ""))
        self.mission_revision = str(data.get("mission_revision", ""))
        self.simulation_only = bool(data.get("simulation_only"))
        self.initial_state_id = str(data.get("initial_state_id", ""))
        self.states: dict[str, dict[str, Any]] = data.get("states", {})
        protocol_catalog_supplied = protocol_ids is not None
        revision_catalog_supplied = protocol_revisions is not None
        normalized_protocol_ids = (
            set(protocol_ids) if protocol_ids is not None else set()
        )
        normalized_protocol_revisions = (
            dict(protocol_revisions) if protocol_revisions is not None else {}
        )
        self.dependency_errors: tuple[str, ...] = ()
        self.dependency_status = "unknown"
        self._validate_definition(
            protocol_ids=normalized_protocol_ids,
            protocol_revisions=normalized_protocol_revisions,
            protocol_catalog_supplied=protocol_catalog_supplied,
            revision_catalog_supplied=revision_catalog_supplied,
            school_profile_id=school_profile_id,
            school_profile=school_profile or {},
        )

    def _validate_definition(
        self,
        *,
        protocol_ids: set[str],
        protocol_revisions: dict[str, int],
        protocol_catalog_supplied: bool,
        revision_catalog_supplied: bool,
        school_profile_id: str | None,
        school_profile: dict[str, Any],
    ) -> None:
        errors: list[str] = []
        dependency_errors: list[str] = []
        if not self.mission_id:
            errors.append("mission_id is required")
        if not self.mission_revision:
            errors.append("mission_revision is required")
        if self.data.get("valid_for_real_emergency") is not False:
            errors.append("development mission must set valid_for_real_emergency=false")
        if not isinstance(self.states, dict) or not self.states:
            errors.append("states must be a non-empty object")
        if self.initial_state_id not in self.states:
            errors.append("initial_state_id is not declared")

        dependency_profile = (
            self.data.get("dependencies", {})
            .get("school_profile", {})
            .get("profile_id")
        )
        if (
            school_profile_id
            and dependency_profile
            and dependency_profile != school_profile_id
        ):
            errors.append(
                "mission school profile does not match the loaded school profile"
            )
        profile_dependency = self.data.get("dependencies", {}).get(
            "school_profile", {}
        )
        if school_profile:
            expected_schema = profile_dependency.get("schema_version")
            expected_status = profile_dependency.get("status_required")
            if expected_schema and school_profile.get("schema_version") != expected_schema:
                errors.append("mission school-profile schema version mismatch")
            if expected_status and school_profile.get("status") != expected_status:
                errors.append("mission school-profile status mismatch")

        required_revisions = self.data.get("dependencies", {}).get(
            "protocol_revisions", {}
        )
        if not isinstance(required_revisions, dict):
            errors.append("dependencies.protocol_revisions must be an object")
        elif revision_catalog_supplied:
            for protocol_id, expected_revision in required_revisions.items():
                actual_revision = protocol_revisions.get(protocol_id)
                if actual_revision != expected_revision:
                    dependency_errors.append(
                        f"protocol revision mismatch for {protocol_id}: "
                        f"expected {expected_revision}, loaded {actual_revision}"
                    )
        elif protocol_catalog_supplied:
            dependency_errors.append("protocol revision catalog was not supplied")

        terminal_ids: list[str] = []
        for state_id, state in self.states.items():
            if not isinstance(state, dict):
                errors.append(f"{state_id}: state must be an object")
                continue
            if state.get("state_id") != state_id:
                errors.append(f"{state_id}: embedded state_id must match its key")
            kind = state.get("kind")
            if kind not in STATE_KINDS:
                errors.append(f"{state_id}: invalid state kind {kind!r}")
            if kind == "terminal":
                terminal_ids.append(state_id)
            context_patch = state.get("context_patch")
            if not isinstance(context_patch, dict):
                errors.append(f"{state_id}: context_patch must be an object")
            calm = state.get("calm", {})
            protocol_id = calm.get("protocol_id")
            if kind == "terminal":
                if protocol_id is not None:
                    errors.append(f"{state_id}: terminal state cannot select a protocol")
            elif not protocol_id:
                errors.append(f"{state_id}: non-terminal state needs a protocol_id")
            elif protocol_catalog_supplied and protocol_id not in protocol_ids:
                dependency_errors.append(
                    f"{state_id}: unavailable protocol_id {protocol_id}"
                )

            transitions = state.get("transitions", [])
            if not isinstance(transitions, list):
                errors.append(f"{state_id}: transitions must be an array")
                continue
            if kind == "terminal" and transitions:
                errors.append(f"{state_id}: terminal state cannot have transitions")
            if kind != "terminal" and not transitions:
                errors.append(f"{state_id}: non-terminal state needs a transition")
            seen_edges: set[tuple[str, str]] = set()
            for transition in transitions:
                if not isinstance(transition, dict):
                    errors.append(f"{state_id}: transition must be an object")
                    continue
                event = transition.get("event")
                target = transition.get("to_state_id")
                edge_kind = transition.get("kind")
                if not event or not isinstance(event, str):
                    errors.append(f"{state_id}: transition event is required")
                if target not in self.states:
                    errors.append(f"{state_id}: unknown transition target {target!r}")
                if edge_kind not in TRANSITION_KINDS:
                    errors.append(
                        f"{state_id}: invalid transition kind {edge_kind!r}"
                    )
                edge = (str(event), str(target))
                if edge in seen_edges:
                    errors.append(f"{state_id}: duplicate transition {edge}")
                seen_edges.add(edge)

        verification = self.data.get("verification")
        if not isinstance(verification, dict):
            errors.append("verification must be an object")
        else:
            verification_question = verification.get("question")
            if not isinstance(verification_question, str) or not verification_question.strip():
                errors.append("verification.question must be a non-empty string")
            callable_ids = {
                state_id
                for state_id, state in self.states.items()
                if isinstance(state, dict) and state.get("kind") != "terminal"
            }
            verification_states = verification.get("states")
            callable_order = verification.get("callable_state_order")
            if not isinstance(verification_states, dict):
                errors.append("verification.states must be an object")
                verification_states = {}
            if not isinstance(callable_order, list) or not all(
                isinstance(item, str) for item in callable_order
            ):
                errors.append(
                    "verification.callable_state_order must be a string array"
                )
                callable_order = []
            elif len(callable_order) != len(set(callable_order)):
                errors.append("verification.callable_state_order has duplicates")
            if set(callable_order) != callable_ids:
                errors.append(
                    "verification.callable_state_order must cover every callable state exactly once"
                )
            if set(verification_states) != callable_ids:
                errors.append(
                    "verification.states must cover every callable state exactly once"
                )
            for state_id, expected in verification_states.items():
                if state_id not in callable_ids or not isinstance(expected, dict):
                    errors.append(f"{state_id}: invalid verification state")
                    continue
                for field in (
                    "expected_movement_authorized",
                    "expected_selected_route_id",
                    "expected_safe_zone_id",
                ):
                    if field not in expected:
                        errors.append(f"{state_id}: verification missing {field}")
                movement = expected.get("expected_movement_authorized")
                route_id = expected.get("expected_selected_route_id")
                zone_id = expected.get("expected_safe_zone_id")
                if not isinstance(movement, bool):
                    errors.append(
                        f"{state_id}: expected_movement_authorized must be boolean"
                    )
                if route_id is not None and not isinstance(route_id, str):
                    errors.append(
                        f"{state_id}: expected_selected_route_id must be string or null"
                    )
                if zone_id is not None and not isinstance(zone_id, str):
                    errors.append(
                        f"{state_id}: expected_safe_zone_id must be string or null"
                    )
                if movement is True and (not route_id or not zone_id):
                    errors.append(
                        f"{state_id}: authorized movement requires an expected route and zone"
                    )
                response_mode = expected.get("response_mode")
                if response_mode not in {"protocol_text", "no_route_fallback"}:
                    errors.append(f"{state_id}: invalid verification response_mode")
                if response_mode == "no_route_fallback" and (
                    movement is not False or route_id is not None
                ):
                    errors.append(
                        f"{state_id}: no-route verification must fail closed"
                    )
                entry = expected.get("entry")
                if not isinstance(entry, dict):
                    errors.append(f"{state_id}: verification entry must be an object")
                    continue
                previous_state_id = entry.get("previous_state_id")
                transition_event = entry.get("transition_event")
                if state_id == self.initial_state_id:
                    if previous_state_id is not None or transition_event != "MISSION_STARTED":
                        errors.append(
                            f"{state_id}: initial verification entry is invalid"
                        )
                elif not isinstance(previous_state_id, str) or not isinstance(
                    transition_event, str
                ):
                    errors.append(f"{state_id}: verification entry is incomplete")
                elif not self._transition_is_allowed(
                    previous_state_id, transition_event, state_id
                ):
                    errors.append(
                        f"{state_id}: verification entry is not a declared transition"
                    )

        if len(terminal_ids) != 1:
            errors.append("mission must declare exactly one terminal state")
        if not errors:
            reachable = self._reachable_from(self.initial_state_id)
            unreachable = sorted(set(self.states) - reachable)
            if unreachable:
                errors.append(f"unreachable states: {', '.join(unreachable)}")
            terminal = terminal_ids[0]
            cannot_finish = sorted(
                state_id
                for state_id in self.states
                if terminal not in self._reachable_from(state_id)
            )
            if cannot_finish:
                errors.append(
                    "states without a path to terminal: " + ", ".join(cannot_finish)
                )
        if errors:
            raise MissionContractError(
                f"Invalid mission contract {self.path.name}: " + "; ".join(errors)
            )
        self.dependency_errors = tuple(sorted(set(dependency_errors)))
        if not protocol_catalog_supplied and not revision_catalog_supplied:
            self.dependency_status = "unknown"
        elif (
            protocol_catalog_supplied
            and revision_catalog_supplied
            and not self.dependency_errors
        ):
            self.dependency_status = "ready"
        else:
            self.dependency_status = "unavailable"

    def _reachable_from(self, start: str) -> set[str]:
        seen: set[str] = set()
        pending = [start]
        while pending:
            state_id = pending.pop()
            if state_id in seen or state_id not in self.states:
                continue
            seen.add(state_id)
            pending.extend(
                str(item["to_state_id"])
                for item in self.states[state_id].get("transitions", [])
            )
        return seen

    def expanded_context(self, state_id: str) -> dict[str, Any]:
        if state_id not in self.states:
            raise MissionContractError(f"Unknown state {state_id!r}")
        expanded: dict[str, Any] = {}
        for source in (
            self.data.get("base_context", {}),
            self.states[state_id].get("context_patch", {}),
        ):
            for key, value in source.items():
                expanded[key] = json.loads(json.dumps(value))
        return expanded

    def _transition_is_allowed(
        self,
        previous_state_id: str,
        event: str,
        current_state_id: str,
    ) -> bool:
        previous = self.states.get(previous_state_id)
        if not previous:
            return False
        return any(
            item.get("event") == event
            and item.get("to_state_id") == current_state_id
            for item in previous.get("transitions", [])
        )

    def validate_context(self, context: dict[str, Any]) -> MissionContextCheck:
        missing: list[str] = []
        invalid: list[str] = []
        conflicts: list[str] = []
        state_id = context.get("state_id")
        if not isinstance(state_id, str):
            state = None
            invalid.append("state_id:MISSION_STATE_ID_NOT_STRING")
        else:
            state = self.states.get(state_id)

        for field in MISSION_METADATA_FIELDS:
            if field not in context:
                missing.append(field)

        mission_revision = context.get("mission_revision")
        if "mission_revision" in context:
            if not isinstance(mission_revision, str) or not mission_revision:
                invalid.append("mission_revision:INVALID_NONEMPTY_STRING")
            elif mission_revision != self.mission_revision:
                conflicts.append("MISSION_REVISION_MISMATCH")
        state_seq = context.get("state_seq")
        previous_state_seq = context.get("previous_state_seq")
        if "state_seq" in context and (
            isinstance(state_seq, bool) or not isinstance(state_seq, int) or state_seq < 1
        ):
            invalid.append("state_seq:INVALID_POSITIVE_INTEGER")
        if "previous_state_seq" in context and (
            isinstance(previous_state_seq, bool)
            or not isinstance(previous_state_seq, int)
            or previous_state_seq < 0
        ):
            invalid.append("previous_state_seq:INVALID_NONNEGATIVE_INTEGER")
        if (
            isinstance(state_seq, int)
            and not isinstance(state_seq, bool)
            and isinstance(previous_state_seq, int)
            and not isinstance(previous_state_seq, bool)
            and state_seq != previous_state_seq + 1
        ):
            conflicts.append("MISSION_SEQUENCE_NOT_MONOTONIC")

        if state is None:
            if isinstance(state_id, str):
                conflicts.append("MISSION_STATE_UNKNOWN")
            if self.dependency_status == "unavailable":
                conflicts.append("MISSION_PROTOCOL_DEPENDENCIES_UNAVAILABLE")
            return MissionContextCheck(
                recognized=True,
                envelope_present=True,
                mission_id=self.mission_id,
                mission_revision=self.mission_revision,
                state_id=str(state_id) if state_id is not None else None,
                simulation_only=self.simulation_only,
                missing=tuple(sorted(set(missing))),
                invalid=tuple(sorted(set(invalid))),
                conflicts=tuple(sorted(set(conflicts))),
                dependency_status=self.dependency_status,
            )

        terminal = state.get("kind") == "terminal"
        if terminal:
            conflicts.append("MISSION_TERMINAL_STATE_DOES_NOT_CALL_ASSISTANT")

        if state_id == self.initial_state_id:
            if context.get("previous_state_id") is not None:
                conflicts.append("MISSION_INITIAL_PREVIOUS_STATE_MUST_BE_NULL")
            if context.get("previous_state_seq") != 0:
                conflicts.append("MISSION_INITIAL_PREVIOUS_SEQUENCE_MUST_BE_ZERO")
            if context.get("transition_event") != "MISSION_STARTED":
                conflicts.append("MISSION_INITIAL_EVENT_INVALID")
        else:
            previous_state_id = context.get("previous_state_id")
            event = context.get("transition_event")
            if not isinstance(previous_state_id, str) or not isinstance(event, str):
                invalid.append("MISSION_TRANSITION_METADATA_INVALID")
            elif not self._transition_is_allowed(previous_state_id, event, state_id):
                conflicts.append("MISSION_TRANSITION_NOT_ALLOWED")

        if self.dependency_status == "unavailable":
            conflicts.append("MISSION_PROTOCOL_DEPENDENCIES_UNAVAILABLE")

        expected_context = self.expanded_context(state_id)
        for field, expected in expected_context.items():
            if field not in context:
                missing.append(field)
            elif context[field] != expected:
                conflicts.append(f"MISSION_CONTEXT_MISMATCH:{field}")

        # Cross-field invariants remain explicit even if a future state patch is
        # edited incorrectly.
        if context.get("shaking_active") is True:
            if context.get("hazard_active") is not True:
                conflicts.append("MISSION_SHAKING_REQUIRES_ACTIVE_HAZARD")
            if context.get("phase") not in {"during", "after"}:
                conflicts.append("MISSION_SHAKING_PHASE_INVALID")
        if context.get("aftershock_active") is True:
            if context.get("phase") != "after":
                conflicts.append("MISSION_AFTERSHOCK_PHASE_INVALID")
            if context.get("shaking_active") is not True:
                conflicts.append("MISSION_AFTERSHOCK_REQUIRES_SHAKING")
        if context.get("at_assembly_area") is True and (
            context.get("location_zone") != "ASSEMBLY_A"
            or context.get("location_type") != "outdoor"
        ):
            conflicts.append("MISSION_ASSEMBLY_LOCATION_INVALID")

        calm = state.get("calm", {})
        allowed_transitions = tuple(
            {
                "event": str(item["event"]),
                "to_state_id": str(item["to_state_id"]),
                "kind": str(item["kind"]),
            }
            for item in state.get("transitions", [])
        )
        return MissionContextCheck(
            recognized=True,
            envelope_present=True,
            mission_id=self.mission_id,
            mission_revision=self.mission_revision,
            state_id=state_id,
            state_label=state.get("label"),
            state_kind=state.get("kind"),
            expected_protocol_id=calm.get("protocol_id"),
            expected_action_code=calm.get("action_code"),
            expected_completion_code=calm.get("expected_completion_code", "OK"),
            enforce_protocol=bool(calm.get("enforce_protocol", True)),
            simulation_only=self.simulation_only,
            terminal=terminal,
            missing=tuple(sorted(set(missing))),
            invalid=tuple(sorted(set(invalid))),
            conflicts=tuple(sorted(set(conflicts))),
            allowed_transitions=allowed_transitions,
            dependency_status=self.dependency_status,
        )

    @property
    def summary(self) -> dict[str, Any]:
        terminal = next(
            state_id
            for state_id, state in self.states.items()
            if state.get("kind") == "terminal"
        )
        return {
            "mission_id": self.mission_id,
            "mission_revision": self.mission_revision,
            "title": self.data.get("title"),
            "simulation_only": self.simulation_only,
            "valid_for_real_emergency": self.data.get("valid_for_real_emergency"),
            "initial_state_id": self.initial_state_id,
            "terminal_state_id": terminal,
            "state_count": len(self.states),
            "main_path": list(self.data.get("main_path", [])),
            "dependency_status": self.dependency_status,
        }


class MissionRegistry:
    """Load all versioned mission contracts available to the API."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        protocol_ids: Iterable[str] | None = None,
        protocol_revisions: dict[str, int] | None = None,
        school_profile_id: str | None = None,
        school_profile: dict[str, Any] | None = None,
    ) -> None:
        self.directory = directory or DEFAULT_MISSIONS_DIR
        self._contracts: dict[str, MissionContract] = {}
        normalized_protocol_ids = (
            tuple(protocol_ids) if protocol_ids is not None else None
        )
        normalized_protocol_revisions = (
            dict(protocol_revisions) if protocol_revisions is not None else None
        )
        if self.directory.exists():
            for path in sorted(self.directory.glob("*.json")):
                contract = MissionContract(
                    path,
                    protocol_ids=normalized_protocol_ids,
                    protocol_revisions=normalized_protocol_revisions,
                    school_profile_id=school_profile_id,
                    school_profile=school_profile,
                )
                if contract.mission_id in self._contracts:
                    raise MissionContractError(
                        f"Duplicate mission_id {contract.mission_id!r}"
                    )
                self._contracts[contract.mission_id] = contract

    def get(self, mission_id: str | None) -> MissionContract | None:
        return self._contracts.get(str(mission_id)) if mission_id else None

    def validate_context(self, context: dict[str, Any]) -> MissionContextCheck:
        contract = self.get(context.get("scenario_id"))
        if not contract:
            envelope_present = any(
                field in context for field in MISSION_METADATA_FIELDS
            )
            mission_id = context.get("scenario_id")
            state_id = context.get("state_id")
            return MissionContextCheck(
                recognized=False,
                envelope_present=envelope_present,
                mission_id=mission_id if isinstance(mission_id, str) else None,
                state_id=state_id if isinstance(state_id, str) else None,
                conflicts=("MISSION_ID_UNKNOWN",) if envelope_present else (),
            )
        return contract.validate_context(context)

    @property
    def summaries(self) -> list[dict[str, Any]]:
        return [contract.summary for contract in self._contracts.values()]

    @property
    def status(self) -> dict[str, Any]:
        unavailable = {
            mission_id: list(contract.dependency_errors)
            for mission_id, contract in self._contracts.items()
            if contract.dependency_status == "unavailable"
        }
        dependency_statuses = {
            contract.dependency_status for contract in self._contracts.values()
        }
        return {
            "loaded_contract_count": len(self._contracts),
            "mission_ids": sorted(self._contracts),
            "contracts_valid": not unavailable,
            "contracts_executable": (
                True
                if dependency_statuses == {"ready"}
                else False
                if "unavailable" in dependency_statuses
                else None
            ),
            "dependency_errors": unavailable,
        }
