from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from calm_core.unity_crosswalk import UnityScenarioCrosswalk, validate_crosswalk


class UnityScenarioCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.crosswalk = UnityScenarioCrosswalk()

    def test_loads_all_implemented_unity_tasks(self) -> None:
        self.assertEqual(self.crosswalk.mission_count, 12)
        self.assertEqual(self.crosswalk.task_count, 90)

    def test_covers_all_three_hazards(self) -> None:
        hazards = {
            mission["hazard"] for mission in self.crosswalk.data["missions"]
        }
        self.assertEqual(hazards, {"earthquake", "fire", "typhoon"})

    def test_scenario_bound_and_evidence_gap_tasks_have_scope_constraints(
        self,
    ) -> None:
        constrained = [
            task
            for mission in self.crosswalk.data["missions"]
            for task in mission["tasks"]
            if task["mapping_status"] in {"scenario_bound", "evidence_gap"}
        ]
        self.assertTrue(constrained)
        self.assertTrue(all(task.get("scope_constraint") for task in constrained))

    def test_retrieval_plan_separates_instruction_from_corpus_evidence(self) -> None:
        plan = self.crosswalk.retrieval_plan("eq_home_6_dch")

        self.assertIn(
            "drop, cover, and hold",
            plan["active_simulation_instruction"].lower(),
        )
        self.assertEqual(
            [
                card["protocol_id"]
                for card in plan["retrieved_safety_evidence"]
            ],
            ["EQ-DUR-001"],
        )
        self.assertEqual(
            [
                card["protocol_id"]
                for card in plan["deviation_safety_evidence"]
            ],
            ["EQ-DUR-003"],
        )
        self.assertEqual(
            plan["retrieval_filters"],
            {"hazard": "earthquake", "phase": "during", "setting": "home"},
        )

    def test_tutorial_ask_task_uses_general_retrieval_mode(self) -> None:
        task = self.crosswalk.get_task("tut_13_ask")
        self.assertIsNotNone(task)
        self.assertTrue(task["general_qa"])

        plan = self.crosswalk.retrieval_plan("tut_13_ask")
        self.assertEqual(plan["retrieval_mode"], "all_supported_hazards")
        self.assertTrue(plan["general_qa"])
        self.assertEqual(
            plan["retrieval_filters"],
            {"hazard": "earthquake", "phase": "before", "setting": "home"},
        )

    def test_v2_home_go_bag_keeps_its_evidence_gap_explicit(self) -> None:
        task = self.crosswalk.get_task("eq_home_a2_gobag")
        self.assertEqual(task["scene"], "Earthquake_Home_V5")
        self.assertEqual(task["mapping_status"], "evidence_gap")
        self.assertEqual(task["protocol_ids"], [])
        self.assertTrue(task["scope_constraint"])

    def test_v2_home_park_task_uses_outdoor_evidence(self) -> None:
        plan = self.crosswalk.retrieval_plan("eq_home_a4_street")
        self.assertEqual(plan["retrieval_filters"]["setting"], "outdoor")
        self.assertEqual(
            [card["protocol_id"] for card in plan["retrieved_safety_evidence"]],
            ["EQ-AFT-003"],
        )

    def test_v2_fire_home_rest_keeps_its_evidence_gap_explicit(self) -> None:
        task = self.crosswalk.get_task("fire_home_b4_rest")
        self.assertEqual(task["scene"], "Fire_Home_V5")
        self.assertEqual(task["mapping_status"], "evidence_gap")
        self.assertEqual(task["protocol_ids"], [])
        self.assertTrue(task["scope_constraint"])

    def test_v2_fire_home_shout_grounds_on_its_during_card_explicitly(self) -> None:
        task = self.crosswalk.get_task("fire_home_a1_alarm")
        self.assertEqual(task["phase"], "after")
        self.assertEqual(task["protocol_ids"], ["FIR-DUR-001"])
        self.assertTrue(task["allow_cross_phase_grounding"])

    def test_v2_typhoon_home_keeps_v1_and_scopes_conflicting_cards(self) -> None:
        missions = {mission["scene"]: mission for mission in self.crosswalk.data["missions"]}
        self.assertEqual(len(missions["Typhoon_Home"]["tasks"]), 9)
        v2 = missions["Typhoon_Home_V5"]["tasks"]
        self.assertEqual(
            [task["task_id"] for task in v2],
            [
                "typ_home_b1_news", "typ_home_b2_pack", "typ_home_b3_loose",
                "typ_home_d1_shelter", "typ_home_d2_flashlight", "typ_home_d3_calm",
                "typ_home_a1_allclear", "typ_home_a2_spot", "typ_home_a3_water",
                "typ_home_a4_dry",
            ],
        )
        for task in v2:
            self.assertFalse(task["required_trusted_flags"]["authenticated_evacuation_order"])
            self.assertTrue(task["scope_constraint"])
        for task_id in ("typ_home_d3_calm", "typ_home_a2_spot", "typ_home_a4_dry"):
            self.assertTrue(self.crosswalk.get_task(task_id)["allow_cross_phase_grounding"])

    def test_unknown_unity_task_is_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "Unknown Unity task_id"):
            self.crosswalk.retrieval_plan("not_a_real_task")

    def test_schema_corpus_references_and_live_unity_validate(self) -> None:
        report = validate_crosswalk()

        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["task_count"], 90)


class UnityReconciliationTests(unittest.TestCase):
    """Prove the Unity drift check actually detects drift.

    This check is the only thing standing between a renamed Unity task and a
    learner asking about a task the backend cannot resolve. It has run green
    since the day it was written, which on its own tells us nothing: a check
    that has never failed has never been shown to work.
    """

    def _library(self, task_ids: list[str]) -> str:
        """Stand-in for MissionLibrary.cs.

        The scanner matches `Id = "..."`, so the stand-in must use that shape.
        Any other spelling reads as a file containing no tasks at all, which
        would make every one of these tests pass for the wrong reason.
        """

        entries = "\n".join(f'            Id = "{t}",' for t in task_ids)
        return f"namespace CALM.Missions {{\n{entries}\n}}\n"

    def _drift(self, task_ids: list[str]) -> list[str]:
        """Reconcile a synthetic library and return only the drift errors.

        A temporary directory has no Unity storyboards beside it, so the
        storyboard check always complains here. That is an artefact of the
        fixture rather than the behaviour under test.
        """

        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "MissionLibrary.cs"
            library.write_text(self._library(task_ids), encoding="utf-8")
            report = validate_crosswalk(unity_library_path=library)
        return [
            error
            for error in report["errors"]
            if "missing from crosswalk" in error or "absent from Unity" in error
        ]

    @property
    def _all_task_ids(self) -> list[str]:
        crosswalk = UnityScenarioCrosswalk()
        return [
            task["task_id"]
            for mission in crosswalk.data["missions"]
            for task in mission["tasks"]
        ]

    def test_matching_library_reconciles_cleanly(self) -> None:
        self.assertEqual(self._drift(self._all_task_ids), [])

    def test_a_task_unity_added_is_reported(self) -> None:
        """Unity gains a task; the backend would 404 on it."""

        drift = self._drift(self._all_task_ids + ["eq_home_9_newthing"])

        self.assertTrue(
            any("missing from crosswalk" in error for error in drift), drift
        )

    def test_a_task_unity_removed_is_reported(self) -> None:
        """Unity drops a task the crosswalk still claims exists."""

        drift = self._drift(self._all_task_ids[:-1])

        self.assertTrue(
            any("absent from Unity" in error for error in drift), drift
        )

    def test_a_renamed_task_is_reported_from_both_sides(self) -> None:
        """The commonest drift: a rename is an add and a removal at once."""

        renamed = self._all_task_ids[:-1] + ["eq_out_5_evacuate"]
        joined = " ".join(self._drift(renamed))

        self.assertIn("missing from crosswalk", joined)
        self.assertIn("absent from Unity", joined)


if __name__ == "__main__":
    unittest.main()
