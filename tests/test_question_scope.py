from __future__ import annotations

import json
import unittest
from pathlib import Path

from calm_core.question_scope import (
    SCOPE_CROSS_HAZARD,
    SCOPE_IN_HAZARD_OFF_TASK,
    SCOPE_ON_TASK,
    SCOPE_OUT_OF_SCOPE,
    classify,
    detect_locale,
    question_hazard,
    question_in_scope,
    question_phase,
)
from calm_core.llm import LLMResult
from calm_core.rag_chat import RAGChatService
from calm_core.unity_crosswalk import UnityScenarioCrosswalk


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "scope_eval.jsonl"


class _StubProvider:
    """Stands in for Ollama so scope decisions are tested without a model."""

    status = {"provider": "test-provider", "model": "test-model"}

    def chat(self, messages):
        return LLMResult(
            text="Stub answer.",
            model="test-model",
            elapsed_ms=1,
            prompt_tokens=1,
            output_tokens=1,
        )


class QuestionInScopeTests(unittest.TestCase):
    def test_disaster_questions_are_in_scope(self) -> None:
        for question in (
            "What should I do now?",
            "Where should I go?",
            "Is the fire exit safe?",
            "Ano ang gagawin ko?",
            "Saan ako pupunta?",
            "May lindol ba?",
        ):
            with self.subTest(question=question):
                self.assertTrue(question_in_scope(question))

    def test_unrelated_questions_are_out_of_scope(self) -> None:
        for question in (
            "What is seven times eight?",
            "Who is the best basketball player?",
            "Can you sing me a song?",
            "What is your favourite colour?",
        ):
            with self.subTest(question=question):
                self.assertFalse(question_in_scope(question))

    def test_plural_hazard_words_are_recognised(self) -> None:
        """'earthquakes' must not read as off-topic just for being plural."""

        self.assertTrue(question_in_scope("Do earthquakes happen often?"))
        self.assertTrue(question_in_scope("Are typhoons dangerous?"))

    def test_empty_question_is_in_scope(self) -> None:
        """No question means the learner is following the cue, not going off-topic."""

        self.assertTrue(question_in_scope(""))
        self.assertTrue(question_in_scope("   "))


class QuestionHazardTests(unittest.TestCase):
    def test_single_hazard_is_identified(self) -> None:
        self.assertEqual(question_hazard("What if there is a fire?"), "fire")
        self.assertEqual(question_hazard("Paano kung may sunog?"), "fire")
        self.assertEqual(question_hazard("What about an earthquake?"), "earthquake")
        self.assertEqual(question_hazard("Ano ang gagawin sa lindol?"), "earthquake")
        self.assertEqual(question_hazard("How strong is the typhoon?"), "typhoon")
        self.assertEqual(question_hazard("Delikado ba ang baha?"), "typhoon")

    def test_ambiguous_multi_hazard_returns_none(self) -> None:
        """Two hazards named at once is not a routable request."""

        self.assertIsNone(question_hazard("Is fire worse than an earthquake?"))
        self.assertIsNone(question_hazard("What about typhoons and fires?"))

    def test_no_hazard_returns_none(self) -> None:
        self.assertIsNone(question_hazard("What should I do now?"))


class QuestionPhaseTests(unittest.TestCase):
    def test_phase_words_are_identified(self) -> None:
        self.assertEqual(
            question_phase("What do I do after the shaking stops?"), "after"
        )
        self.assertEqual(question_phase("Ano ang gagawin pagkatapos?"), "after")
        self.assertEqual(question_phase("How do I prepare?"), "before")
        self.assertEqual(question_phase("Ano ang paghahanda?"), "before")

    def test_ambiguous_phase_returns_none(self) -> None:
        self.assertIsNone(question_phase("What do I do before and after?"))

    def test_no_phase_returns_none(self) -> None:
        self.assertIsNone(question_phase("Is the table sturdy?"))

    def test_dialogue_timing_words_do_not_invent_a_disaster_phase(self) -> None:
        for question in (
            "What should I do now?",
            "Ano ang gagawin ko ngayon?",
            "What should I do next?",
            "Ano ang susunod?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(question_phase(question))


class DetectLocaleTests(unittest.TestCase):
    """A child should not have to set a dropdown before every question."""

    def test_english_question_gets_english(self) -> None:
        for question in (
            "What should I do now?",
            "Why should I not touch it?",
            "Where is the exit?",
        ):
            with self.subTest(question=question):
                self.assertEqual(detect_locale(question), "en-PH")

    def test_filipino_question_gets_filipino(self) -> None:
        for question in (
            "Ano ang dapat kong gawin?",
            "bakit ganyan? pano gagawin ko",
            "paano ako magiging ligtas",
        ):
            with self.subTest(question=question):
                self.assertEqual(detect_locale(question), "fil-PH")

    def test_mixed_question_gets_taglish(self) -> None:
        """'What if may lindol?' is not a pure Filipino question."""

        self.assertEqual(detect_locale("What if may lindol?"), "taglish-PH")

    def test_empty_question_falls_back_to_the_default(self) -> None:
        self.assertEqual(detect_locale("", default="fil-PH"), "fil-PH")


class FailOpenTests(unittest.TestCase):
    """Refusing a real safety question is worse than answering a stray one.

    Every question below was refused by the earlier fail-closed gate, which
    demanded a hazard word and turned away any phrasing that lacked one.
    """

    def test_real_safety_questions_are_not_refused(self) -> None:
        for question in (
            "Why should I not touch it?",
            "bakit hindi ko dapat galawin",
            "bakit kailangan ko maging aware after the shock",
            "ano ang dapat kong gawin ngayon",
            "is this one okay to pick up?",
        ):
            with self.subTest(question=question):
                scope = classify(
                    question, task_hazard="earthquake", task_phase="before"
                )
                self.assertNotEqual(scope.scope, SCOPE_OUT_OF_SCOPE)

    def test_plainly_unrelated_questions_are_still_refused(self) -> None:
        for question in (
            "What is seven times eight?",
            "Who is the best basketball player?",
            "Can you sing me a song?",
            "Ano ang paborito mong pagkain?",
            "Pwede mo ba akong bilhan ng laruan?",
        ):
            with self.subTest(question=question):
                scope = classify(
                    question, task_hazard="earthquake", task_phase="before"
                )
                self.assertEqual(scope.scope, SCOPE_OUT_OF_SCOPE)


class ClassifyTests(unittest.TestCase):
    def test_same_hazard_same_phase_is_on_task(self) -> None:
        scope = classify(
            "What should I do now?", task_hazard="earthquake", task_phase="during"
        )
        self.assertEqual(scope.scope, SCOPE_ON_TASK)
        self.assertTrue(scope.is_answerable)

    def test_now_and_next_remain_on_the_active_task_in_any_phase(self) -> None:
        for question in (
            "What should I do now?",
            "What should I do next?",
            "Ano ang gagawin ko ngayon?",
            "Ano ang susunod?",
        ):
            with self.subTest(question=question):
                scope = classify(
                    question, task_hazard="typhoon", task_phase="after"
                )
                self.assertEqual(scope.scope, SCOPE_ON_TASK)
                self.assertIsNone(scope.asked_phase)

    def test_other_hazard_is_cross_hazard_in_both_directions(self) -> None:
        fire_during_earthquake = classify(
            "What if there is a fire?", task_hazard="earthquake", task_phase="during"
        )
        self.assertEqual(fire_during_earthquake.scope, SCOPE_CROSS_HAZARD)
        self.assertEqual(fire_during_earthquake.asked_hazard, "fire")

        earthquake_during_fire = classify(
            "What about an earthquake?", task_hazard="fire", task_phase="during"
        )
        self.assertEqual(earthquake_during_fire.scope, SCOPE_CROSS_HAZARD)
        self.assertEqual(earthquake_during_fire.asked_hazard, "earthquake")

    def test_same_hazard_other_phase_is_in_hazard_off_task(self) -> None:
        scope = classify(
            "What do I do after the shaking stops?",
            task_hazard="earthquake",
            task_phase="during",
        )
        self.assertEqual(scope.scope, SCOPE_IN_HAZARD_OFF_TASK)
        self.assertEqual(scope.asked_phase, "after")

    def test_unrelated_question_is_out_of_scope_and_unanswerable(self) -> None:
        scope = classify(
            "What is seven times eight?",
            task_hazard="earthquake",
            task_phase="during",
        )
        self.assertEqual(scope.scope, SCOPE_OUT_OF_SCOPE)
        self.assertFalse(scope.is_answerable)

    def test_hazard_beats_phase_when_both_differ(self) -> None:
        """A different hazard is the stronger signal; it decides the branch."""

        scope = classify(
            "What do I do after a fire?",
            task_hazard="earthquake",
            task_phase="during",
        )
        self.assertEqual(scope.scope, SCOPE_CROSS_HAZARD)


class ScopeGoldenSetTests(unittest.TestCase):
    """Replay the reviewed question set so lexicon edits cannot drift silently."""

    def setUp(self) -> None:
        self.crosswalk = UnityScenarioCrosswalk()
        self.service = RAGChatService(_StubProvider(), self.crosswalk)
        with FIXTURE.open(encoding="utf-8") as stream:
            self.rows = [json.loads(line) for line in stream if line.strip()]

    def test_fixture_covers_every_scope_hazard_and_locale(self) -> None:
        scopes = {row["expected_scope"] for row in self.rows}
        hazards = {
            self.crosswalk.get_task(row["task_id"])["hazard"] for row in self.rows
        }
        locales = {row["locale"] for row in self.rows}
        self.assertEqual(
            scopes,
            {
                SCOPE_ON_TASK,
                SCOPE_IN_HAZARD_OFF_TASK,
                SCOPE_CROSS_HAZARD,
                SCOPE_OUT_OF_SCOPE,
            },
        )
        self.assertEqual(hazards, {"earthquake", "fire", "typhoon"})
        self.assertEqual(locales, {"en-PH", "fil-PH", "taglish-PH"})

    def test_every_task_id_in_the_fixture_exists(self) -> None:
        for row in self.rows:
            with self.subTest(task_id=row["task_id"]):
                self.assertIsNotNone(self.crosswalk.get_task(row["task_id"]))

    def test_every_golden_question_scopes_as_reviewed(self) -> None:
        """Assert the scope the service settles on, not the bare lexicon.

        The service also weighs the active task's own vocabulary, so this is the
        decision that actually reaches a learner.
        """

        for row in self.rows:
            with self.subTest(question=row["question"], task=row["task_id"]):
                result = self.service.answer(
                    question=row["question"],
                    task_id=row["task_id"],
                    locale=row["locale"],
                )
                self.assertEqual(result["question_scope"], row["expected_scope"])

    def test_no_golden_question_is_answered_from_mismatched_evidence(self) -> None:
        """A cross-hazard answer must never cite the active task's hazard."""

        prefixes = {"earthquake": "EQ", "fire": "FIR", "typhoon": "TYP"}
        for row in self.rows:
            if row["expected_scope"] != "cross_hazard":
                continue
            with self.subTest(question=row["question"], task=row["task_id"]):
                result = self.service.answer(
                    question=row["question"],
                    task_id=row["task_id"],
                    locale=row["locale"],
                )
                if result["evidence_scope"] != "asked_hazard_evidence":
                    continue
                asked = prefixes[result["asked_hazard"]]
                for evidence_id in result["retrieved_evidence_ids"]:
                    self.assertTrue(evidence_id.startswith(asked), evidence_id)


if __name__ == "__main__":
    unittest.main()
