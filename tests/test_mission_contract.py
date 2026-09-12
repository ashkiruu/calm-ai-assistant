from __future__ import annotations

import unittest

from calm_core.repository import ProtocolRepository
from calm_core.router import CALMAssistant


MISSION_ID = "school-earthquake-minimal"
TIMESTAMP = "2026-07-31T10:00:00+08:00"


class EarthquakeSchoolMissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assistant = CALMAssistant(corpus_mode="development")
        cls.contract = cls.assistant.missions.get(MISSION_ID)
        if cls.contract is None:
            raise AssertionError("EQ School mission contract did not load")

    def context(
        self,
        state_id: str,
        *,
        previous_state_id: str | None,
        transition_event: str,
        state_seq: int,
        previous_state_seq: int | None = None,
        **changes,
    ):
        context = self.contract.expanded_context(state_id)
        context.update(
            {
                "session_id": "mission-test-random-001",
                "scenario_id": MISSION_ID,
                "state_id": state_id,
                "mission_revision": self.contract.mission_revision,
                "state_seq": state_seq,
                "previous_state_seq": (
                    state_seq - 1
                    if previous_state_seq is None
                    else previous_state_seq
                ),
                "previous_state_id": previous_state_id,
                "transition_event": transition_event,
                "timestamp": TIMESTAMP,
            }
        )
        context.update(changes)
        return context

    def respond(self, context, question="What should I do?"):
        return self.assistant.respond(
            question=question,
            context=context,
            locale="en-PH",
        )

    def event_between(self, source_id: str, target_id: str) -> str:
        for transition in self.contract.states[source_id]["transitions"]:
            if transition["to_state_id"] == target_id:
                return transition["event"]
        raise AssertionError(f"No transition from {source_id} to {target_id}")

    def test_contract_has_one_reachable_ending_and_canonical_main_path(self):
        summary = self.contract.summary
        self.assertEqual(summary["state_count"], 17)
        self.assertEqual(summary["initial_state_id"], "EQ-S-B01")
        self.assertEqual(summary["terminal_state_id"], "EQ-S-END")
        self.assertEqual(summary["main_path"][-2:], ["EQ-S-A07", "EQ-S-END"])
        self.assertTrue(summary["simulation_only"])
        self.assertFalse(summary["valid_for_real_emergency"])

    def test_full_main_path_selects_the_frozen_state_protocols(self):
        path = self.contract.data["main_path"]
        previous = None
        expected_protocols = []
        actual_protocols = []
        for index, state_id in enumerate(path[:-1], start=1):
            event = (
                "MISSION_STARTED"
                if previous is None
                else self.event_between(previous, state_id)
            )
            result = self.respond(
                self.context(
                    state_id,
                    previous_state_id=previous,
                    transition_event=event,
                    state_seq=index,
                )
            )
            expected = self.contract.states[state_id]["calm"]["protocol_id"]
            expected_protocols.append(expected)
            actual_protocols.append(result["protocol_id"])
            with self.subTest(state_id=state_id):
                self.assertEqual(result["context_status"], "valid")
                self.assertEqual(result["mission"]["contract_status"], "valid")
                self.assertEqual(result["protocol_id"], expected)
                self.assertEqual(
                    result["completion_or_error_code"],
                    self.contract.states[state_id]["calm"][
                        "expected_completion_code"
                    ],
                )
                self.assertFalse(result["llm_used"])
            previous = state_id
        self.assertEqual(actual_protocols, expected_protocols)

    def test_during_correction_loops_return_to_protection(self):
        cases = [
            (
                "EQ-S-D02",
                "EQ-S-D01",
                "RUN_TO_EXIT_ATTEMPTED",
                5,
                "EQ-DUR-003",
            ),
            (
                "EQ-S-D03",
                "EQ-S-D04",
                "GLASS_OR_SHELF_APPROACH_ATTEMPTED",
                7,
                "EQ-DUR-002",
            ),
        ]
        for state_id, previous, event, seq, expected in cases:
            with self.subTest(state_id=state_id):
                correction = self.respond(
                    self.context(
                        state_id,
                        previous_state_id=previous,
                        transition_event=event,
                        state_seq=seq,
                    )
                )
                self.assertEqual(correction["protocol_id"], expected)
                returned = self.respond(
                    self.context(
                        "EQ-S-D04",
                        previous_state_id=state_id,
                        transition_event="SAFE_COVER_RESTORED",
                        state_seq=seq + 1,
                    )
                )
                self.assertEqual(returned["protocol_id"], "EQ-DUR-001")
                self.assertEqual(returned["context_status"], "valid")

    def test_glass_correction_has_reachable_approved_cover(self):
        context = self.contract.expanded_context("EQ-S-D03")
        state = self.contract.states["EQ-S-D03"]

        self.assertTrue(context["approved_cover_reachable"])
        self.assertTrue(context["near_falling_or_glass_hazard"])
        self.assertIn(
            "MOVE_SHORT_DISTANCE_TO_APPROVED_COVER",
            state["learner_actions"]["permitted"],
        )

    def test_no_route_holds_then_trusted_update_selects_alternate(self):
        hold = self.respond(
            self.context(
                "EQ-S-H01-NO-ROUTE",
                previous_state_id="EQ-S-A03",
                transition_event="ROUTE_REVOKED",
                state_seq=10,
            )
        )
        self.assertEqual(hold["protocol_id"], "EQ-AFT-001")
        self.assertEqual(
            hold["completion_or_error_code"], "NO_APPROVED_OPEN_ROUTE"
        )
        self.assertIsNone(hold["selected_route_id"])
        self.assertFalse(hold["movement_authorized"])

        retry = self.respond(
            self.context(
                "EQ-S-A03",
                previous_state_id="EQ-S-H01-NO-ROUTE",
                transition_event="ROUTE_UPDATED_FOR_TRAVEL",
                state_seq=11,
            )
        )
        self.assertEqual(
            retry["selected_route_id"], "ROUTE_CLASSROOM_A_ALTERNATE"
        )
        self.assertTrue(retry["movement_authorized"])

    def test_report_pending_clears_without_erasing_known_concern(self):
        resumed = self.respond(
            self.context(
                "EQ-S-A04R",
                previous_state_id="EQ-S-A06",
                transition_event="AFTERSHOCK_STOPPED",
                state_seq=12,
            )
        )
        self.assertEqual(resumed["protocol_id"], "EQ-AFT-008")
        self.assertEqual(resumed["action_code"], "SCHOOL_ASSEMBLY_HEADCOUNT")

    def test_unknown_jump_is_rejected_before_protocol_selection(self):
        invalid = self.respond(
            self.context(
                "EQ-S-A04",
                previous_state_id="EQ-S-B01",
                transition_event="ASSEMBLY_TRIGGER_REACHED",
                state_seq=2,
            )
        )
        self.assertEqual(invalid["context_status"], "conflicting")
        self.assertEqual(invalid["completion_or_error_code"], "CONTEXT_CONFLICT")
        self.assertIsNone(invalid["protocol_id"])
        self.assertIn("MISSION_TRANSITION_NOT_ALLOWED", invalid["decision_trace"])

    def test_state_zone_mismatch_is_rejected(self):
        invalid = self.respond(
            self.context(
                "EQ-S-A04",
                previous_state_id="EQ-S-A03",
                transition_event="ASSEMBLY_TRIGGER_REACHED",
                state_seq=9,
                location_zone="CLASSROOM_A",
                location_type="indoors",
            )
        )
        self.assertEqual(invalid["context_status"], "conflicting")
        self.assertIn(
            "MISSION_CONTEXT_MISMATCH:location_zone",
            invalid["decision_trace"],
        )

    def test_out_of_order_sequence_is_rejected(self):
        invalid = self.respond(
            self.context(
                "EQ-S-B02",
                previous_state_id="EQ-S-B01",
                transition_event="APPROVED_COVER_IDENTIFIED",
                state_seq=4,
                previous_state_seq=1,
            )
        )
        self.assertEqual(invalid["context_status"], "conflicting")
        self.assertIn(
            "MISSION_SEQUENCE_NOT_MONOTONIC", invalid["decision_trace"]
        )

    def test_terminal_state_must_not_call_assistant(self):
        invalid = self.respond(
            self.context(
                "EQ-S-END",
                previous_state_id="EQ-S-A07",
                transition_event="REENTRY_CORRECTED",
                state_seq=14,
            )
        )
        self.assertEqual(invalid["context_status"], "conflicting")
        self.assertIn(
            "MISSION_TERMINAL_STATE_DOES_NOT_CALL_ASSISTANT",
            invalid["decision_trace"],
        )

    def test_alarm_that_conflicts_with_phase_is_rejected(self):
        invalid = self.respond(
            self.context(
                "EQ-S-A01",
                previous_state_id="EQ-S-D04",
                transition_event="SHAKING_STOPPED",
                state_seq=6,
                alarm_id="SIM_EQ_SHAKING_CUE",
            )
        )
        self.assertEqual(invalid["context_status"], "conflicting")
        self.assertIn("ALARM_PHASE_CONFLICT", invalid["decision_trace"])

    def test_unknown_mission_envelope_is_rejected_instead_of_bypassing(self):
        context = self.context(
            "EQ-S-B01",
            previous_state_id=None,
            transition_event="MISSION_STARTED",
            state_seq=1,
        )
        context["scenario_id"] = "school-earthquake-typo"
        result = self.respond(context)
        self.assertEqual(result["context_status"], "conflicting")
        self.assertEqual(result["completion_or_error_code"], "CONTEXT_CONFLICT")
        self.assertIsNone(result["protocol_id"])
        self.assertFalse(result["mission"]["recognized"])
        self.assertEqual(result["mission"]["contract_status"], "rejected")
        self.assertIn("MISSION_ID_UNKNOWN", result["decision_trace"])

    def test_malformed_registered_state_id_fails_closed_without_exception(self):
        context = self.context(
            "EQ-S-B01",
            previous_state_id=None,
            transition_event="MISSION_STARTED",
            state_seq=1,
        )
        context["state_id"] = ["EQ-S-B01"]
        result = self.respond(context)
        self.assertEqual(result["context_status"], "invalid")
        self.assertEqual(result["completion_or_error_code"], "CONTEXT_INVALID")
        self.assertIsNone(result["protocol_id"])

    def test_initial_mission_metadata_rejects_explicit_nulls(self):
        fields = (
            "mission_revision",
            "state_seq",
            "previous_state_seq",
            "transition_event",
        )
        for field in fields:
            with self.subTest(field=field):
                context = self.context(
                    "EQ-S-B01",
                    previous_state_id=None,
                    transition_event="MISSION_STARTED",
                    state_seq=1,
                )
                context[field] = None
                result = self.respond(context)
                self.assertNotEqual(result["context_status"], "valid")
                self.assertIsNone(result["protocol_id"])

    def test_mission_revision_must_be_nonempty_and_exact(self):
        for value, expected_status in (
            ("", "invalid"),
            ("0.0.0-wrong", "conflicting"),
        ):
            with self.subTest(value=value):
                context = self.context(
                    "EQ-S-B01",
                    previous_state_id=None,
                    transition_event="MISSION_STARTED",
                    state_seq=1,
                )
                context["mission_revision"] = value
                result = self.respond(context)
                self.assertEqual(result["context_status"], expected_status)
                self.assertIsNone(result["protocol_id"])

    def test_noninitial_transition_metadata_rejects_explicit_nulls(self):
        for field in (
            "previous_state_id",
            "previous_state_seq",
            "transition_event",
        ):
            with self.subTest(field=field):
                context = self.context(
                    "EQ-S-B02",
                    previous_state_id="EQ-S-B01",
                    transition_event="APPROVED_COVER_IDENTIFIED",
                    state_seq=2,
                )
                context[field] = None
                result = self.respond(context)
                self.assertEqual(result["context_status"], "invalid")
                self.assertEqual(
                    result["completion_or_error_code"], "CONTEXT_INVALID"
                )
                self.assertIsNone(result["protocol_id"])

    def test_empty_supplied_production_catalog_marks_contract_unexecutable(self):
        production = CALMAssistant(
            repository=ProtocolRepository(mode="production")
        )
        status = production.missions.status
        self.assertFalse(status["contracts_valid"])
        self.assertFalse(status["contracts_executable"])
        self.assertIn(MISSION_ID, status["dependency_errors"])

        context = self.context(
            "EQ-S-B01",
            previous_state_id=None,
            transition_event="MISSION_STARTED",
            state_seq=1,
        )
        result = production.respond(
            question="What should I do?", context=context, locale="en-PH"
        )
        self.assertEqual(result["context_status"], "conflicting")
        self.assertIsNone(result["protocol_id"])
        self.assertIn(
            "MISSION_PROTOCOL_DEPENDENCIES_UNAVAILABLE",
            result["decision_trace"],
        )


if __name__ == "__main__":
    unittest.main()
