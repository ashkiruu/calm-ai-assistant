"""Exercise every Unity task for learner-agency regressions.

This is an evaluation harness, not an answer authority. It calls the same local
RAG service Unity uses and applies conservative, inspectable heuristics to find
answers that may replace an available learner action with adult dependence.
Human review is still required for every finding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from calm_core.llm import OllamaClient
from calm_core.rag_chat import MAX_ANSWER_WORDS, RAGChatService
from calm_core.unity_crosswalk import UnityScenarioCrosswalk


AUTHORITY_WORDS = re.compile(
    r"\b(?:teacher|guardian|adult|responder|grown[- ]?up|authority|firefighter)\b",
    re.I,
)
DEPENDENCY_PHRASE = re.compile(
    r"\b(?:ask|tell|inform|wait\s+for|stay\s+with|follow)\b[^.!?]{0,55}"
    r"\b(?:teacher|guardian|adult|responder|grown[- ]?up|authority|firefighter)\b",
    re.I,
)
INTERNAL_WORDS = re.compile(
    r"\b(?:protocol|card|source|(?:EQ|FIR|TYP)-(?:BEF|DUR|AFT)-\d{3})\b",
    re.I,
)
TOKEN = re.compile(r"[a-zA-Z]+")
STOPWORDS = {
    "a", "an", "and", "as", "at", "away", "be", "before", "configured",
    "current", "down", "for", "from", "in", "into", "it", "of", "on",
    "over", "prop", "safe", "simulated", "simulation", "the", "then", "this",
    "through", "to", "training", "up", "use", "using", "vr", "with", "your",
}
SHORT_ACTION_TERMS = {"low", "out", "run"}


def content_terms(text: str) -> set[str]:
    return {
        word
        for word in TOKEN.findall(text.casefold())
        if (len(word) >= 4 or word in SHORT_ACTION_TERMS) and word not in STOPWORDS
    }


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]


def covers_step(answer: str, step: str) -> bool:
    step_terms = content_terms(step)
    return len(content_terms(answer) & step_terms) >= min(2, len(step_terms))


def evaluate(
    *,
    plan: dict[str, Any],
    answers: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    instruction = plan["active_simulation_instruction"]
    instruction_terms = content_terms(instruction)
    instruction_has_authority = bool(AUTHORITY_WORDS.search(instruction))
    practice_bound = plan["mapping_status"] in {"scenario_bound", "evidence_gap"}

    for case, result in answers.items():
        text = result["response_text"]
        answer_terms = content_terms(text)
        overlap = instruction_terms & answer_terms
        prefix = first_sentence(text)

        if INTERNAL_WORDS.search(text):
            findings.append({"case": case, "code": "INTERNAL_METADATA", "text": text})
        if len(text.split()) > MAX_ANSWER_WORDS:
            findings.append({"case": case, "code": "TOO_LONG", "text": text})
        if result["question_scope"] != "on_task":
            findings.append(
                {
                    "case": case,
                    "code": "NOT_ON_TASK",
                    "text": f'{result["question_scope"]}: {text}',
                }
            )
        if not overlap:
            findings.append({"case": case, "code": "NO_TASK_ACTION_OVERLAP", "text": text})
        if (
            practice_bound
            and not instruction_has_authority
            and AUTHORITY_WORDS.search(text)
        ):
            findings.append(
                {"case": case, "code": "PRACTICE_REPLACED_BY_AUTHORITY", "text": text}
            )
        if case in {"normal", "alone"} and DEPENDENCY_PHRASE.search(prefix) and not (
            instruction_terms & content_terms(prefix)
        ):
            findings.append(
                {"case": case, "code": "AUTHORITY_BEFORE_SELF_ACTION", "text": text}
            )

    steps = plan.get("practice_steps", [])
    if steps:
        missing = [step for step in steps if not covers_step(answers["how"]["response_text"], step)]
        if missing:
            findings.append(
                {
                    "case": "how",
                    "code": "MISSING_CONFIGURED_PRACTICE_STEP",
                    "text": " | ".join(missing),
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    crosswalk = UnityScenarioCrosswalk()
    service = RAGChatService(OllamaClient(timeout_seconds=args.timeout), crosswalk)
    task_ids = crosswalk.task_ids
    rows: list[dict[str, Any]] = []

    for index, task_id in enumerate(task_ids, 1):
        print(f"[{index:02d}/{len(task_ids)}] {task_id}", file=sys.stderr, flush=True)
        plan = crosswalk.retrieval_plan(task_id)
        normal = service.answer(
            question="What should I do now?", task_id=task_id, locale="en-PH"
        )
        alone = service.answer(
            question=(
                "There is no teacher or guardian nearby. "
                "What can I safely do myself right now?"
            ),
            task_id=task_id,
            locale="en-PH",
        )
        how = service.answer(
            question="How do I do that?",
            task_id=task_id,
            locale="en-PH",
            previous_question=alone["question"],
            previous_response=alone["response_text"],
        )
        answers = {"normal": normal, "alone": alone, "how": how}
        rows.append(
            {
                "task_id": task_id,
                "scene": plan["scene"],
                "mapping_status": plan["mapping_status"],
                "active_simulation_instruction": plan["active_simulation_instruction"],
                "practice_steps": plan.get("practice_steps", []),
                "answers": {
                    name: {
                        "question": result["question"],
                        "response_text": result["response_text"],
                        "question_scope": result["question_scope"],
                        "answer_source": result["answer_source"],
                    }
                    for name, result in answers.items()
                },
                "findings": evaluate(plan=plan, answers=answers),
            }
        )

    report = {
        "prompt_policy_version": service.status["prompt_policy_version"],
        "task_count": len(rows),
        "answer_count": len(rows) * 3,
        "tasks_with_findings": sum(bool(row["findings"]) for row in rows),
        "finding_count": sum(len(row["findings"]) for row in rows),
        "rows": rows,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    print(
        f'AUDIT: {report["answer_count"]} answers, '
        f'{report["tasks_with_findings"]} tasks with findings, '
        f'{report["finding_count"]} findings.',
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
