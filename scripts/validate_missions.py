"""Validate every executable CALM mission against the live deterministic core."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calm_core.router import CALMAssistant


def incoming_edges(contract) -> dict[str, list[tuple[str, str]]]:
    incoming = {state_id: [] for state_id in contract.states}
    for source_id, state in contract.states.items():
        for transition in state.get("transitions", []):
            incoming[transition["to_state_id"]].append(
                (source_id, transition["event"])
            )
    return incoming


def context_for(contract, state_id: str, incoming) -> dict:
    context = contract.expanded_context(state_id)
    if state_id == contract.initial_state_id:
        previous_state_id = None
        previous_state_seq = 0
        state_seq = 1
        event = "MISSION_STARTED"
    else:
        previous_state_id, event = incoming[state_id][0]
        previous_state_seq = 1
        state_seq = 2
    context.update(
        {
            "session_id": f"validator-{state_id.lower()}",
            "scenario_id": contract.mission_id,
            "mission_revision": contract.mission_revision,
            "state_id": state_id,
            "state_seq": state_seq,
            "previous_state_seq": previous_state_seq,
            "previous_state_id": previous_state_id,
            "transition_event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return context


def main() -> int:
    assistant = CALMAssistant(corpus_mode="development")
    errors: list[str] = []
    checked_states = 0
    terminal_states = 0

    for summary in assistant.missions.summaries:
        contract = assistant.missions.get(summary["mission_id"])
        if contract is None:
            errors.append(f"missing loaded contract {summary['mission_id']}")
            continue
        incoming = incoming_edges(contract)
        for state_id, state in contract.states.items():
            if state.get("kind") == "terminal":
                terminal_states += 1
                continue
            checked_states += 1
            result = assistant.respond(
                question="What should I do?",
                context=context_for(contract, state_id, incoming),
                locale="en-PH",
            )
            calm = state["calm"]
            checks = {
                "context_status": (result["context_status"], "valid"),
                "mission_status": (
                    result["mission"]["contract_status"],
                    "valid",
                ),
                "protocol_id": (result["protocol_id"], calm["protocol_id"]),
                "action_code": (result["action_code"], calm["action_code"]),
                "completion": (
                    result["completion_or_error_code"],
                    calm["expected_completion_code"],
                ),
                "llm_used": (result["llm_used"], False),
            }
            for label, (actual, expected) in checks.items():
                if actual != expected:
                    errors.append(
                        f"{contract.mission_id}/{state_id} {label}: "
                        f"{actual!r} != {expected!r}"
                    )

    report = {
        "status": "PASS" if not errors else "FAIL",
        "mission_contract_count": len(assistant.missions.summaries),
        "callable_state_count": checked_states,
        "terminal_state_count": terminal_states,
        "corpus_runtime_approved": assistant.repository.status[
            "runtime_approved"
        ],
        "school_valid_for_real_emergency": assistant.school.status[
            "valid_for_real_emergency"
        ],
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
