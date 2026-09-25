"""Every answer draws its evidence from one lesson phase.

The regression this guards: the Tutorial's ask-anything task pooled before,
during and after cards into one prompt, and an alphabetical tie-break ranked
after-phase cards first ("AFT" < "BEF" < "DUR").  "What should I do in an
earthquake?" came back with four cards and no Drop, Cover and Hold On.

The sweep covers every crosswalk task, not a hand-picked few, so a new task or
a new card cannot reintroduce the mix without failing here.
"""

from __future__ import annotations

import unittest

from calm_core.llm import LLMResult
from calm_core.question_scope import (
    SCOPE_CROSS_HAZARD,
    SCOPE_IN_HAZARD_OFF_TASK,
    SCOPE_ON_TASK,
)
from calm_core.rag_chat import RAGChatService
from calm_core.repository import PHASE_ORDER


class _Provider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    @property
    def status(self):
        return {"provider": "test-provider", "model": "test-model"}

    def chat(self, messages):
        self.calls.append(messages)
        return LLMResult(
            text="Grounded test answer.",
            model="test-model",
            elapsed_ms=1,
            prompt_tokens=1,
            output_tokens=1,
        )


#: One question per stage, each naming its stage without naming a hazard.
PHASE_QUESTIONS = {
    "before": "How do I get ready before it happens?",
    "during": "What do I do while it is happening?",
    "after": "What do I do after it is over?",
}
OTHER_HAZARD_QUESTIONS = {
    "earthquake": "What should I do in a fire?",
    "fire": "What should I do in an earthquake?",
    "typhoon": "What should I do in a fire?",
}
GENERAL_QUESTIONS = (
    "What should I do in a fire?",
    "What should I do in an earthquake?",
    "What do I do if there is a flood?",
    "Ano ang gagawin ko kapag may sunog?",
    "How do I stay safe?",
    "What should I pack in a go bag?",
    "Is it safe to go back inside?",
    "What should I do when the shaking stops?",
    "How do I prepare for a typhoon?",
    "What is disaster preparedness?",
)


class PhaseCoherenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = _Provider()
        cls.service = RAGChatService(cls.provider)
        cls.phase = {
            card["protocol_id"]: card["classification"]["phase"]
            for card in cls.service.repository.cards
        }
        cls.hazard = {
            card["protocol_id"]: card["classification"]["hazard"]
            for card in cls.service.repository.cards
        }
        cls.tasks = [
            cls.service.crosswalk.get_task(task_id)
            for task_id in cls.service.crosswalk.task_ids
        ]

    def _phases(self, ids: list[str]) -> set[str]:
        return {self.phase[item] for item in ids}

    def test_on_task_questions_use_exactly_the_task_cards(self) -> None:
        for task in self.tasks:
            if task.get("general_qa"):
                continue
            with self.subTest(task=task["task_id"]):
                result = self.service.answer(
                    question="What should I do now?", task_id=task["task_id"]
                )
                self.assertEqual(result["question_scope"], SCOPE_ON_TASK)
                self.assertEqual(
                    result["retrieved_evidence_ids"], task["protocol_ids"]
                )

    def test_a_question_about_another_stage_never_mixes_stages(self) -> None:
        for task in self.tasks:
            if task.get("general_qa"):
                continue
            for asked_phase, question in PHASE_QUESTIONS.items():
                if asked_phase == task["phase"]:
                    continue
                with self.subTest(task=task["task_id"], asked=asked_phase):
                    calls_before = len(self.provider.calls)
                    result = self.service.answer(
                        question=question, task_id=task["task_id"]
                    )
                    self.assertEqual(
                        result["question_scope"], SCOPE_IN_HAZARD_OFF_TASK
                    )
                    ids = result["retrieved_evidence_ids"]
                    if result["deferred_question"]:
                        # A live task: the reviewed cue and a promise, never the
                        # model improvising another stage from this one's card.
                        self.assertEqual(
                            result["completion_code"],
                            "DEFERRED_DURING_CRITICAL_TASK",
                        )
                        self.assertEqual(len(self.provider.calls), calls_before)
                        self.assertEqual(ids, task["protocol_ids"])
                        continue
                    self.assertEqual(result["evidence_scope"], "asked_phase_evidence")
                    self.assertEqual(self._phases(ids), {asked_phase})
                    self.assertEqual(
                        {self.hazard[item] for item in ids}, {task["hazard"]}
                    )

    def test_a_question_about_another_hazard_uses_one_stage_of_that_hazard(self) -> None:
        for task in self.tasks:
            if task.get("general_qa"):
                continue
            question = OTHER_HAZARD_QUESTIONS[task["hazard"]]
            with self.subTest(task=task["task_id"]):
                result = self.service.answer(
                    question=question, task_id=task["task_id"]
                )
                self.assertEqual(result["question_scope"], SCOPE_CROSS_HAZARD)
                ids = result["retrieved_evidence_ids"]
                if result["deferred_question"]:
                    self.assertEqual(ids, task["protocol_ids"])
                    continue
                self.assertEqual(
                    {self.hazard[item] for item in ids}, {result["asked_hazard"]}
                )
                # No stage named: "what do I do in a fire?" means during.
                self.assertEqual(self._phases(ids), {"during"})

    def test_general_questions_draw_from_a_single_stage(self) -> None:
        for question in GENERAL_QUESTIONS:
            with self.subTest(question=question):
                result = self.service.answer(question=question, task_id="tut_13_ask")
                ids = result["retrieved_evidence_ids"]
                self.assertTrue(ids)
                self.assertEqual(len(self._phases(ids)), 1, ids)

    def test_a_named_hazard_without_a_stage_means_during(self) -> None:
        result = self.service.answer(
            question="What should I do in an earthquake?", task_id="tut_13_ask"
        )
        self.assertEqual(self._phases(result["retrieved_evidence_ids"]), {"during"})
        # The canonical indoor action leads, not a card that merely shared "an".
        self.assertEqual(result["retrieved_evidence_ids"][0], "EQ-DUR-001")

    def test_a_named_stage_wins(self) -> None:
        for phase, question in (
            ("before", "How do I prepare for a typhoon?"),
            ("after", "What should I do after an earthquake?"),
            ("after", "What should I do when the shaking stops?"),
        ):
            with self.subTest(question=question):
                result = self.service.answer(question=question, task_id="tut_13_ask")
                self.assertEqual(
                    self._phases(result["retrieved_evidence_ids"]), {phase}
                )


class CorpusOrderTests(unittest.TestCase):
    def test_cards_are_stored_hazard_then_lesson_phase(self) -> None:
        service = RAGChatService(_Provider())
        keys = [
            (
                card["classification"]["hazard"],
                PHASE_ORDER.index(card["classification"]["phase"]),
                card["protocol_id"],
            )
            for card in service.repository.cards
        ]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
