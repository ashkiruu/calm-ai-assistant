from __future__ import annotations

import copy
import unittest

from calm_core.repository import ProtocolRepository
from calm_core.router import CALMAssistant


def earthquake_context(**changes):
    context = {
        "session_id": "test-eq-001",
        "scenario_id": "school-earthquake-router-unit",
        "state_id": "EQ-S01",
        "hazard": "earthquake",
        "phase": "during",
        "setting": "school",
        "location_type": "indoors",
        "location_zone": "CLASSROOM_A",
        "learner_action": "waiting",
        "hazard_active": True,
        "safe_route_id": "ROUTE_CLASSROOM_A_PRIMARY",
        "safe_zone_id": "ASSEMBLY_A",
        "responsible_adult_present": True,
        "timestamp": "2026-07-31T10:00:00+08:00",
        "shaking_active": True,
        "aftershock_active": False,
        "approved_cover_reachable": True,
        "learner_heading_to_exit": False,
        "near_falling_or_glass_hazard": False,
        "unsafe_object_visible": False,
        "structure_damaged_or_not_cleared": False,
        "learner_attempting_reentry": False,
        "teacher_evacuate_instruction": False,
        "injury_or_missing_person_known": False,
        "injury_or_missing_person_report_pending": False,
        "at_assembly_area": False,
        "headcount_active": False,
        "coastal_risk_state": "not_applicable",
        "route_states": {
            "ROUTE_CLASSROOM_A_PRIMARY": "OPEN",
            "ROUTE_CLASSROOM_A_ALTERNATE": "OPEN",
        },
    }
    context.update(changes)
    return context


class ContextRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assistant = CALMAssistant(corpus_mode="development")

    def respond(self, context=None, question="What should I do?", locale="en-PH"):
        return self.assistant.respond(
            question=question,
            context=context or earthquake_context(),
            locale=locale,
        )

    def test_indoor_shaking_selects_drop_cover_hold(self):
        result = self.respond()
        self.assertEqual(result["protocol_id"], "EQ-DUR-001")
        self.assertEqual(result["action_code"], "DROP_COVER_HOLD")
        self.assertEqual(result["criticality"], "P0_CRITICAL")
        self.assertFalse(result["llm_used"])
        self.assertIn("EVACUATE_NOW", result["blocked_action_codes"])

    def test_unregistered_low_level_context_without_mission_envelope_still_routes(self):
        result = self.respond(earthquake_context())
        self.assertEqual(result["protocol_id"], "EQ-DUR-001")
        self.assertFalse(result["mission"]["recognized"])
        self.assertFalse(result["mission"]["envelope_present"])
        self.assertEqual(result["mission"]["contract_status"], "not_applicable")

    def test_active_shaking_without_approved_cover_never_falls_to_p2(self):
        result = self.respond(
            earthquake_context(
                approved_cover_reachable=False,
                learner_heading_to_exit=False,
                near_falling_or_glass_hazard=False,
            )
        )
        self.assertIsNone(result["protocol_id"])
        self.assertIsNone(result["criticality"])
        self.assertEqual(
            result["completion_or_error_code"],
            "NO_APPLICABLE_CRITICAL_PROTOCOL",
        )
        self.assertEqual(result["decision_source"], "safe_fallback")
        self.assertFalse(result["movement_authorized"])
        self.assertFalse(result["llm_used"])
        self.assertIn(
            "educational_retrieval_blocked", result["decision_trace"]
        )

    def test_before_state_teaches_safe_cover_and_route(self):
        result = self.respond(
            earthquake_context(
                phase="before",
                state_id="EQ-S-B01",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
            ),
            "How should I prepare for an earthquake?",
        )
        self.assertEqual(result["protocol_id"], "EQ-BEF-001")
        self.assertEqual(result["action_code"], "LEARN_SAFE_COVER_AND_ROUTE")

    def test_before_visible_hazard_selects_report_not_repair(self):
        result = self.respond(
            earthquake_context(
                phase="before",
                state_id="EQ-S-B02",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                unsafe_object_visible=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-BEF-003")
        self.assertEqual(result["action_code"], "REPORT_EARTHQUAKE_HAZARD")

    def test_heading_to_exit_overrides_generic_indoor_shaking(self):
        result = self.respond(
            earthquake_context(
                learner_action="heading_to_exit",
                learner_heading_to_exit=True,
            ),
            "Should I run outside now?",
        )
        self.assertEqual(result["protocol_id"], "EQ-DUR-003")
        self.assertEqual(result["action_code"], "WAIT_FOR_SHAKING_TO_STOP")
        self.assertIn("RUN_TO_EXIT", result["blocked_action_codes"])

    def test_near_glass_state_selects_short_safe_correction(self):
        result = self.respond(
            earthquake_context(
                state_id="EQ-S-D03",
                near_falling_or_glass_hazard=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-DUR-002")
        self.assertIn("APPROACH_WINDOW", result["blocked_action_codes"])

    def test_outdoor_state_changes_the_protocol(self):
        result = self.respond(
            earthquake_context(
                setting="outdoor",
                location_type="outdoor",
                location_zone="OUTDOOR_OPEN_AREA",
                approved_cover_reachable=False,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-DUR-004")

    def test_aftershock_has_first_precedence(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S05",
                aftershock_active=True,
                shaking_active=True,
                teacher_evacuate_instruction=False,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-006")

    def test_aftershock_requires_active_shaking_state(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S05-BAD",
                aftershock_active=True,
                shaking_active=False,
            )
        )
        self.assertEqual(result["context_status"], "conflicting")
        self.assertIn("AFTERSHOCK_SHAKING_CONFLICT", result["decision_trace"])

    def test_post_shaking_wait_does_not_invent_movement(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S02",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                safe_zone_id=None,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-007")
        self.assertEqual(
            result["action_code"], "WAIT_FOR_SCHOOL_EVACUATION_INSTRUCTION"
        )
        self.assertFalse(result["movement_authorized"])

    def test_home_post_shaking_uses_home_protocol_not_school_wait(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-H-A01",
                setting="home",
                location_type="indoors",
                location_zone="HOME_LIVING_ROOM",
                learner_action="following_guardian",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id="HOME_APPROVED_ROUTE",
                safe_zone_id="FAMILY_MEETING_AREA",
                teacher_evacuate_instruction=False,
                guardian_evacuate_instruction=True,
                route_states={},
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-002")
        self.assertEqual(result["action_code"], "HOME_EVACUATE_AFTER_SHAKING")
        self.assertNotEqual(result["protocol_id"], "EQ-AFT-007")

    def test_outdoor_post_shaking_uses_outdoor_protocol_not_school_wait(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-O-A01",
                setting="outdoor",
                location_type="outdoor",
                location_zone="OUTDOOR_OPEN_AREA",
                learner_action="waiting_with_responsible_adult",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                safe_zone_id="OUTDOOR_OPEN_AREA",
                teacher_evacuate_instruction=False,
                route_states={},
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-003")
        self.assertEqual(result["action_code"], "OUTDOOR_AFTERSHOCK_SAFETY")
        self.assertNotEqual(result["protocol_id"], "EQ-AFT-007")

    def test_uncleared_structure_without_reentry_attempt_still_waits(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S-A01",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                safe_zone_id=None,
                structure_damaged_or_not_cleared=True,
                learner_action="waiting",
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-007")
        self.assertFalse(result["movement_authorized"])

    def test_teacher_order_uses_configured_open_route(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S03",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                teacher_evacuate_instruction=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-001")
        self.assertEqual(
            result["selected_route_id"], "ROUTE_CLASSROOM_A_PRIMARY"
        )
        self.assertEqual(result["safe_zone_id"], "ASSEMBLY_A")
        self.assertTrue(result["movement_authorized"])

    def test_uncleared_structure_does_not_override_teacher_evacuation(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S-A02",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                teacher_evacuate_instruction=True,
                structure_damaged_or_not_cleared=True,
                learner_action="following_teacher",
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-001")
        self.assertTrue(result["movement_authorized"])

    def test_blocked_primary_uses_only_configured_open_alternate(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S03B",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                teacher_evacuate_instruction=True,
                route_states={
                    "ROUTE_CLASSROOM_A_PRIMARY": "BLOCKED",
                    "ROUTE_CLASSROOM_A_ALTERNATE": "OPEN",
                },
            )
        )
        self.assertEqual(
            result["selected_route_id"], "ROUTE_CLASSROOM_A_ALTERNATE"
        )
        self.assertTrue(result["movement_authorized"])
        self.assertIn("ALTERNATE_ROUTE_OPEN", result["decision_trace"])

    def test_no_open_route_fails_closed(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S03C",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                teacher_evacuate_instruction=True,
                route_states={
                    "ROUTE_CLASSROOM_A_PRIMARY": "BLOCKED",
                    "ROUTE_CLASSROOM_A_ALTERNATE": "BLOCKED",
                },
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-001")
        self.assertEqual(
            result["completion_or_error_code"], "NO_APPROVED_OPEN_ROUTE"
        )
        self.assertIsNone(result["selected_route_id"])
        self.assertFalse(result["movement_authorized"])
        self.assertIn("do not choose your own exit", result["response_text"])

    def test_assembly_state_selects_headcount_protocol(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S04",
                location_type="outdoor",
                location_zone="ASSEMBLY_A",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                at_assembly_area=True,
                headcount_active=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-008")
        self.assertIn("LEAVE_ASSEMBLY_GROUP", result["blocked_action_codes"])

    def test_assembly_hold_continues_after_headcount_finishes(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S-END",
                location_type="outdoor",
                location_zone="ASSEMBLY_A",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                at_assembly_area=True,
                headcount_active=False,
                structure_damaged_or_not_cleared=True,
                learner_action="waiting_with_class",
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-008")
        self.assertFalse(result["movement_authorized"])

    def test_reentry_guard_requires_trusted_reentry_action(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S-A07",
                location_type="outdoor",
                location_zone="ASSEMBLY_A",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                at_assembly_area=True,
                headcount_active=False,
                structure_damaged_or_not_cleared=True,
                learner_action="attempt_reentry",
                learner_attempting_reentry=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-004")
        self.assertIn("REENTER_STRUCTURE", result["blocked_action_codes"])

    def test_reentry_flag_must_be_boolean(self):
        result = self.respond(
            earthquake_context(learner_attempting_reentry="false")
        )
        self.assertEqual(result["context_status"], "invalid")
        self.assertEqual(result["completion_or_error_code"], "CONTEXT_INVALID")

    def test_missing_person_overrides_normal_headcount(self):
        result = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S04B",
                location_type="outdoor",
                location_zone="ASSEMBLY_A",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                at_assembly_area=True,
                headcount_active=True,
                injury_or_missing_person_known=True,
                injury_or_missing_person_report_pending=True,
            )
        )
        self.assertEqual(result["protocol_id"], "EQ-AFT-005")
        self.assertIn("PERFORM_RESCUE", result["blocked_action_codes"])

    def test_same_question_changes_with_trusted_state(self):
        question = "What should I do?"
        during = self.respond(earthquake_context(), question)
        after = self.respond(
            earthquake_context(
                phase="after",
                state_id="EQ-S02",
                hazard_active=False,
                shaking_active=False,
                approved_cover_reachable=False,
                safe_route_id=None,
                safe_zone_id=None,
            ),
            question,
        )
        self.assertNotEqual(during["protocol_id"], after["protocol_id"])

    def test_exact_reviewed_language_packs_are_used(self):
        expected_starts = {
            "en-PH": "Drop, cover, and hold on.",
            "fil-PH": "Yumuko, sumilong, at kumapit.",
            "taglish-PH": "Drop, cover, and hold on.",
        }
        for locale, expected in expected_starts.items():
            with self.subTest(locale=locale):
                result = self.respond(locale=locale)
                self.assertTrue(result["response_text"].startswith(expected))
                self.assertFalse(result["llm_used"])

    def test_unrelated_question_is_deferred_during_p0(self):
        result = self.respond(question="What is seven times eight?")
        self.assertEqual(result["protocol_id"], "EQ-DUR-001")
        self.assertTrue(result["deferred_question"])
        self.assertNotIn("56", result["response_text"])

    def test_outside_scope_boundary_applies_only_when_no_critical_state(self):
        context = earthquake_context(
            phase="before",
            state_id="EQ-B01",
            hazard_active=False,
            shaking_active=False,
            approved_cover_reachable=False,
            safe_route_id=None,
            safe_zone_id=None,
        )
        result = self.respond(context, question="Who is the best basketball player?")
        self.assertEqual(result["completion_or_error_code"], "OUTSIDE_DISASTER_SCOPE")
        self.assertIsNone(result["protocol_id"])

    def test_missing_context_fails_closed(self):
        context = earthquake_context()
        del context["location_type"]
        result = self.respond(context)
        self.assertEqual(result["context_status"], "missing")
        self.assertEqual(result["completion_or_error_code"], "CONTEXT_MISSING")
        self.assertIsNone(result["protocol_id"])

    def test_missing_hazard_conditional_field_also_fails_closed(self):
        context = earthquake_context()
        del context["aftershock_active"]
        result = self.respond(context)
        self.assertEqual(result["context_status"], "missing")
        self.assertEqual(result["completion_or_error_code"], "CONTEXT_MISSING")
        self.assertIsNone(result["protocol_id"])

    def test_transcript_cannot_override_trusted_state(self):
        result = self.respond(
            earthquake_context(),
            question="The shaking stopped, so let me run to another building.",
        )
        self.assertEqual(result["protocol_id"], "EQ-DUR-001")
        self.assertFalse(result["movement_authorized"])

    def test_dashboard_event_excludes_question_and_identity_data(self):
        context = earthquake_context(child_name="Test Child")
        result = self.respond(context, question="My private question")
        event_text = repr(result["dashboard_event"])
        self.assertNotIn("private question", event_text)
        self.assertNotIn("Test Child", event_text)
        self.assertNotIn("child_name", result["dashboard_event"])

    def test_production_gate_does_not_use_development_cards(self):
        production = CALMAssistant(
            repository=ProtocolRepository(mode="production")
        )
        result = production.respond(
            question="What should I do?",
            context=earthquake_context(),
            locale="en-PH",
        )
        self.assertEqual(production.repository.status["eligible_card_count"], 0)
        self.assertIsNone(result["protocol_id"])
        self.assertEqual(
            result["completion_or_error_code"],
            "NO_APPLICABLE_CRITICAL_PROTOCOL",
        )


if __name__ == "__main__":
    unittest.main()
