"""Replay the reviewed question set against the live local model.

The unit suite stubs the provider, so it proves the service routes correctly but
never that the model obeys the prompt.  This script closes that gap: it runs the
same questions through real Ollama and prints what a learner would actually see.

It is a manual review gate, not part of `unittest discover` -- it needs Ollama
running and takes seconds per generated answer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calm_core.llm import LLMUnavailable, OllamaClient
from calm_core.rag_chat import RAGChatService
from calm_core.unity_crosswalk import UnityScenarioCrosswalk


DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "scope_eval.jsonl"
HAZARD_PREFIX = {"earthquake": "EQ", "fire": "FIR", "typhoon": "TYP"}


def _load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _check_grounding(row: dict[str, str], result: dict) -> list[str]:
    """Flag answers whose evidence does not match the hazard actually asked."""

    problems: list[str] = []
    if result["question_scope"] != row["expected_scope"]:
        problems.append(
            f"scope {result['question_scope']} != expected {row['expected_scope']}"
        )
    if result["evidence_scope"] == "asked_hazard_evidence":
        wanted = HAZARD_PREFIX[result["asked_hazard"]]
        wrong = [
            item
            for item in result["retrieved_evidence_ids"]
            if not item.startswith(wanted)
        ]
        if wrong:
            problems.append(f"evidence outside asked hazard: {wrong}")
    if result["llm_used"] and result["question_scope"] == "out_of_scope":
        problems.append("model was called for an out-of-scope question")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--scope",
        help="only replay rows with this expected scope",
    )
    args = parser.parse_args()

    rows = _load(args.fixture)
    if args.scope:
        rows = [row for row in rows if row["expected_scope"] == args.scope]

    service = RAGChatService(OllamaClient(), UnityScenarioCrosswalk())
    generated = 0
    flagged: list[tuple[dict[str, str], list[str]]] = []

    for index, row in enumerate(rows, start=1):
        try:
            result = service.answer(
                question=row["question"],
                task_id=row["task_id"],
                locale=row["locale"],
            )
        except LLMUnavailable as error:
            print(f"\nStopped: {error}", file=sys.stderr)
            return 2

        problems = _check_grounding(row, result)
        if problems:
            flagged.append((row, problems))
        if result["llm_used"]:
            generated += 1

        marker = "!!" if problems else "  "
        engine = (
            f"{result['generation']['elapsed_ms']} ms"
            if result["llm_used"]
            else "no model call"
        )
        print(f"{marker} [{index}/{len(rows)}] {row['task_id']} ({row['locale']})")
        print(f"     Q: {row['question']}")
        print(f"     A: {result['response_text']}")
        print(
            f"     {result['question_scope']} / {result['completion_code']} / "
            f"{result['retrieved_evidence_ids']} / {engine}"
        )
        for problem in problems:
            print(f"     ** {problem}")
        print()

    print("-" * 68)
    print(f"replayed {len(rows)} questions, {generated} reached the model")
    print(f"flagged  {len(flagged)}")
    for row, problems in flagged:
        print(f"  {row['task_id']}: {row['question']} -> {'; '.join(problems)}")
    print()
    print("Answers still need a human read: no automated check can tell whether")
    print("a fluent sentence is safe advice for a Grade 4 learner.")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
