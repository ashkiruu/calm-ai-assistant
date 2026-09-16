"""Score local models against the reviewed question set and write a report.

Model choice for a safety-critical assistant is not a matter of which model is
cleverest.  The prompt states ten ordered rules; the question is which model
obeys them.  Every check here is deterministic and derived from a rule the
prompt actually makes, so the result is auditable rather than impressionistic.

No LLM judges another LLM: a judge would be one more unverified component.

    python scripts/benchmark_models.py --models llama3.2 qwen2.5:3b phi3.5
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calm_core.llm import LLMUnavailable, OllamaClient
from calm_core.rag_chat import MAX_ANSWER_WORDS, RAGChatService
from calm_core.unity_crosswalk import UnityScenarioCrosswalk


DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "scope_eval.jsonl"
DEFAULT_REPORT = ROOT / "docs" / "MODEL_BENCHMARK.md"

#: Imported, never restated.  This file used to hard-code 30 words and a
#: single-sentence rule; the prompt was later relaxed to three sentences and 45
#: words, and nothing failed loudly -- the benchmark simply went on penalising
#: every model for obeying the prompt it was actually given.  The 79 %
#: "single sentence" score recorded for qwen2.5:3b in docs/MODEL_BENCHMARK.md
#: is that artifact, not a model weakness.  Scoring a rule the prompt does not
#: state is worse than not scoring it, so both numbers now come from the prompt.
MAX_WORDS = MAX_ANSWER_WORDS
#: "one to three short, calm sentences" -- rag_chat.py's answer rules.
MAX_SENTENCES = 3
HAZARD_PREFIX = {"earthquake": "EQ", "fire": "FIR", "typhoon": "TYP"}
#: Words the prompt forbids outright, plus any surviving identifier.
FORBIDDEN = ("protocol", "card", "source", "protokol")
LEAKED_ID = re.compile(r"\b(?:EQ|FIR|TYP)-(?:BEF|DUR|AFT)-\d{3}\b", re.I)
#: Function words that mark Filipino output.  Crude by design: it only has to
#: separate "Manatili sa ilalim ng mesa" from an English sentence.
FILIPINO_MARKERS = {
    "ang", "ng", "sa", "mga", "ka", "mo", "ay", "na", "at", "iyong",
    "huwag", "manatili", "guro", "kung", "para", "ito", "hanggang",
}
SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def score_answer(row: dict[str, str], result: dict) -> dict[str, bool]:
    """Check one answer against the rules the prompt states."""

    text = result["response_text"]
    words = text.split()
    lowered = text.casefold()

    # A deterministic reply is text the service authored, not the model.  The
    # length and sentence rules are addressed to the model, so scoring them on
    # a reviewed fallback measures the fallback's wording and penalises every
    # model identically for output none of them produced.
    generated = result["llm_used"]

    checks = {
        # "Never use the words 'protocol', 'card', 'source', or any identifier"
        "no_leaked_terms": not any(term in lowered for term in FORBIDDEN)
        and not LEAKED_ID.search(text),
        # the answer must be in the locale that was asked for
        "correct_locale": True,
        # the reported grounding must match what was actually answered
        "evidence_matches_hazard": True,
        # the scope gate must land where the reviewed set says
        "scope_correct": result["question_scope"] == row["expected_scope"],
    }
    if generated:
        # "one to three short, calm sentences and no more than 45 words total"
        checks["within_word_cap"] = len(words) <= MAX_WORDS
        checks["within_sentence_cap"] = (
            len(SENTENCE_END.findall(text.strip())) <= MAX_SENTENCES
        )

    if row["locale"] in {"fil-PH", "taglish-PH"}:
        spoken = {word.strip(".,!?").casefold() for word in words}
        checks["correct_locale"] = bool(spoken & FILIPINO_MARKERS)

    if result["evidence_scope"] == "asked_hazard_evidence":
        wanted = HAZARD_PREFIX[result["asked_hazard"]]
        checks["evidence_matches_hazard"] = all(
            item.startswith(wanted) for item in result["retrieved_evidence_ids"]
        )

    return checks


def run_model(
    model: str, rows: list[dict[str, str]], crosswalk, load_timeout: float
) -> dict:
    # Only one model fits in 4 GB of VRAM, so switching models evicts the
    # previous one and reloads from disk.  The warm-up call therefore needs a
    # far longer timeout than any real request will ever use.
    warmup = RAGChatService(
        OllamaClient(model=model, timeout_seconds=load_timeout), crosswalk
    )
    try:
        warmup.answer(question="What should I do now?", task_id="eq_home_6_dch")
    except LLMUnavailable as error:
        return {"model": model, "error": f"failed to load: {error}"}

    service = RAGChatService(OllamaClient(model=model), crosswalk)

    totals: dict[str, int] = {}
    # Checks apply to different numbers of rows, so each carries its own
    # denominator rather than being reported against the full question count.
    applicable: dict[str, int] = {}
    latencies: list[int] = []
    generated = 0
    failures: list[tuple[dict[str, str], str, list[str]]] = []

    for row in rows:
        started = time.time()
        try:
            result = service.answer(
                question=row["question"],
                task_id=row["task_id"],
                locale=row["locale"],
            )
        except LLMUnavailable as error:
            return {"model": model, "error": str(error)}
        elapsed = int((time.time() - started) * 1000)

        checks = score_answer(row, result)
        for name, passed in checks.items():
            totals[name] = totals.get(name, 0) + int(passed)
            applicable[name] = applicable.get(name, 0) + 1

        # A deterministic reply is the service's text, not the model's, so it
        # would flatter every model equally.  Only generated answers are timed.
        if result["llm_used"]:
            generated += 1
            latencies.append(elapsed)

        broken = [name for name, passed in checks.items() if not passed]
        if broken:
            failures.append((row, result["response_text"], broken))

    return {
        "model": model,
        "rows": len(rows),
        "generated": generated,
        "totals": totals,
        "applicable": applicable,
        "median_ms": int(statistics.median(latencies)) if latencies else 0,
        "p90_ms": int(sorted(latencies)[int(len(latencies) * 0.9) - 1])
        if latencies
        else 0,
        "failures": failures,
    }


CHECK_LABELS = {
    "scope_correct": "Scope routed correctly",
    "no_leaked_terms": "No internal terms leaked",
    "within_word_cap": f"Within {MAX_WORDS}-word cap",
    "within_sentence_cap": f"At most {MAX_SENTENCES} sentences",
    "correct_locale": "Answered in asked locale",
    "evidence_matches_hazard": "Evidence matches hazard",
}


def render(reports: list[dict], fixture: Path) -> str:
    good = [r for r in reports if "error" not in r]
    lines = [
        "# Local model benchmark",
        "",
        f"Generated {date.today().isoformat()} from `{fixture.relative_to(ROOT)}`.",
        "",
        "Every check below is a rule the system prompt actually states, checked",
        "deterministically. No model judges another model.",
        "",
        "## Compliance",
        "",
    ]

    if not good:
        lines.append("No model completed the run.")
        return "\n".join(lines)

    header = "| Check | " + " | ".join(r["model"] for r in good) + " |"
    lines += [header, "|" + "---|" * (len(good) + 1)]
    for key, label in CHECK_LABELS.items():
        cells = []
        for report in good:
            passed = report["totals"].get(key, 0)
            possible = report["applicable"].get(key, 0)
            cells.append(
                f"{passed}/{possible} ({100 * passed // possible}%)"
                if possible
                else "n/a"
            )
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    overall = []
    for report in good:
        passed = sum(report["totals"].values())
        possible = sum(report["applicable"].values())
        overall.append(f"**{100 * passed // possible}%**" if possible else "n/a")
    lines.append("| **Overall** | " + " | ".join(overall) + " |")
    lines += [
        "",
        "The word-cap and sentence-cap rules are addressed to the model, so",
        "they are scored only on generated answers. The remaining checks apply",
        "to every reply, including the deterministic ones.",
    ]

    lines += ["", "## Latency", "", "Warm, GPU-resident; model load excluded.", ""]
    lines += [
        "| Metric | " + " | ".join(r["model"] for r in good) + " |",
        "|" + "---|" * (len(good) + 1),
        "| Median | " + " | ".join(f"{r['median_ms']} ms" for r in good) + " |",
        "| p90 | " + " | ".join(f"{r['p90_ms']} ms" for r in good) + " |",
        "| Answers generated | "
        + " | ".join(f"{r['generated']}/{r['rows']}" for r in good)
        + " |",
    ]

    lines += ["", "## Rule violations", ""]
    for report in good:
        lines += [f"### {report['model']}", ""]
        if not report["failures"]:
            lines += ["No violations.", ""]
            continue
        for row, text, broken in report["failures"][:12]:
            lines += [
                f"- **{row['question']}** (`{row['task_id']}`, {row['locale']})",
                f"  - answer: {text}",
                f"  - failed: {', '.join(broken)}",
            ]
        if len(report["failures"]) > 12:
            lines.append(f"- ...and {len(report['failures']) - 12} more")
        lines.append("")

    failed = [r for r in reports if "error" in r]
    if failed:
        lines += ["## Did not run", ""]
        lines += [f"- `{r['model']}`: {r['error']}" for r in failed]
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--load-timeout",
        type=float,
        default=300.0,
        help="seconds allowed for the one-off model load before timing",
    )
    args = parser.parse_args()

    rows = load_rows(args.fixture)
    crosswalk = UnityScenarioCrosswalk()

    reports = []
    for model in args.models:
        print(f"running {model} over {len(rows)} questions...", flush=True)
        report = run_model(model, rows, crosswalk, args.load_timeout)
        if "error" in report:
            print(f"  FAILED: {report['error']}", file=sys.stderr)
        else:
            passed = sum(report["totals"].values())
            # Each check carries its own denominator -- the word and sentence
            # caps apply only to generated answers, not to deterministic
            # fallbacks.  Multiplying the check count by the row count assumes
            # every check applies to every row, which under-reports the score
            # and disagreed with the report file for the same run.
            possible = sum(report["applicable"].values())
            print(
                f"  {100 * passed // possible}% compliant, "
                f"median {report['median_ms']} ms",
                flush=True,
            )
        reports.append(report)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render(reports, args.fixture), encoding="utf-8")
    # A report written outside the repo is normal -- a scratch comparison, or a
    # Colab run where the checkout lives somewhere else entirely.  relative_to
    # raises on those, and it used to do so AFTER every model had been scored
    # and the file written, turning a finished run into a traceback.
    try:
        shown = args.report.relative_to(ROOT)
    except ValueError:
        shown = args.report.resolve()
    print(f"\nwrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
