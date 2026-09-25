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
from calm_core.openrouter import OpenRouterClient
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


#: Checks that describe the SERVICE, not the model.  They are identical for
#: every model because the deterministic pipeline produces them, so including
#: them in a model's score measures our own code and flatters everyone equally.
PIPELINE_CHECKS = ("scope_correct", "evidence_matches_hazard")
#: Checks that describe the TEXT THE MODEL WROTE.  Scored only on rows the model
#: actually answered.
MODEL_CHECKS = (
    "no_leaked_terms",
    "correct_locale",
    "within_word_cap",
    "within_sentence_cap",
)


def score_answer(row: dict[str, str], result: dict) -> dict[str, bool]:
    """Check one answer, scoring model rules only where the model answered.

    A check is simply absent from the returned dict when it does not apply, and
    the caller tracks per-check denominators, so an omitted check costs nothing
    rather than counting as a pass.

    This split is the whole point.  Scoring a deterministic fallback as though
    the model wrote it is how a model id that does not exist reached 94 %
    overall: the reviewed fallback passes every text rule by construction, so a
    model that answers less scores higher.  Measured on the real sweep, the
    three DeepSeek variants and ling-3.0-flash answered 19-25 of 44 and topped
    the table on exactly that effect.
    """

    text = result["response_text"]
    words = text.split()
    lowered = text.casefold()
    generated = result["llm_used"]

    checks: dict[str, bool] = {
        # the scope gate must land where the reviewed set says
        "scope_correct": result["question_scope"] == row["expected_scope"],
        # the reported grounding must match what was actually answered
        "evidence_matches_hazard": True,
    }
    if result["evidence_scope"] == "asked_hazard_evidence":
        wanted = HAZARD_PREFIX[result["asked_hazard"]]
        checks["evidence_matches_hazard"] = all(
            item.startswith(wanted) for item in result["retrieved_evidence_ids"]
        )

    if not generated:
        return checks

    # "Never use the words 'protocol', 'card', 'source', or any identifier"
    checks["no_leaked_terms"] = not any(
        term in lowered for term in FORBIDDEN
    ) and not LEAKED_ID.search(text)
    # "one to three short, calm sentences and no more than 45 words total"
    checks["within_word_cap"] = len(words) <= MAX_WORDS
    checks["within_sentence_cap"] = (
        len(SENTENCE_END.findall(text.strip())) <= MAX_SENTENCES
    )
    # Only scored where there is something to get wrong.  An English answer to
    # an English question is not evidence of anything; 19 of the 44 reviewed
    # questions are Filipino or Taglish and those are the discriminating ones.
    if row["locale"] in {"fil-PH", "taglish-PH"}:
        spoken = {word.strip(".,!?").casefold() for word in words}
        checks["correct_locale"] = bool(spoken & FILIPINO_MARKERS)

    return checks


def split_spec(spec: str, default_provider: str) -> tuple[str, str]:
    """Split `openrouter:qwen/qwen3-32b` into provider and model.

    A per-model prefix rather than a whole-run flag, so the local control and a
    dozen hosted models land in ONE comparison table.  Two runs into two report
    files cannot be read against each other, which defeats the point.

    Ollama tags carry a colon too (`qwen2.5:3b`), so only a leading segment that
    names a known provider counts -- split once, and only on that.
    """

    head, _, rest = spec.partition(":")
    if rest and head in PROVIDERS:
        return head, rest
    return default_provider, spec


def make_client(provider: str, model: str, timeout: float | None):
    if provider == "openrouter":
        return OpenRouterClient(model=model, timeout_seconds=timeout)
    return OllamaClient(model=model, timeout_seconds=timeout)


PROVIDERS = ("ollama", "openrouter")


def run_model(
    spec: str, rows: list[dict[str, str]], crosswalk, load_timeout: float,
    default_provider: str,
) -> dict:
    provider, model = split_spec(spec, default_provider)

    if provider == "ollama":
        # Only one model fits in VRAM, so switching models evicts the previous
        # one and reloads from disk.  The warm-up call therefore needs a far
        # longer timeout than any real request will ever use.
        warmup = RAGChatService(
            make_client(provider, model, load_timeout), crosswalk
        )
        try:
            warmup.answer(question="What should I do now?", task_id="eq_home_d1_dch")
        except LLMUnavailable as error:
            return {"model": spec, "provider": provider,
                    "error": f"failed to load: {error}"}
    # A hosted model has nothing to evict and no weights to page in, so the
    # warm-up would buy nothing and cost one request per model -- which matters
    # against a rate limit far more than it does against a disk read.

    service = RAGChatService(make_client(provider, model, None), crosswalk)

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
            return {"model": spec, "provider": provider, "error": str(error)}
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

    if generated == 0:
        # Every reply was a deterministic fallback, so nothing here describes the
        # model -- it describes the reviewed cards.  Scoring it anyway is not a
        # harmless inaccuracy: a model id that does not exist comes back at the
        # same overall percentage as a working one, because the fallback passes
        # scope, evidence and leaked-term checks 44/44 by construction.  Refuse
        # to report a score rather than publish a silent tie.
        return {
            "model": spec,
            "provider": provider,
            "error": "produced no answers; every reply was a deterministic "
                     "fallback, so there is nothing about the model to score",
        }

    return {
        "model": spec,
        "provider": provider,
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


def render(
    reports: list[dict], fixture: Path, pending: list[str] | None = None
) -> str:
    good = [r for r in reports if "error" not in r]
    lines = [
        "# Local model benchmark",
        "",
        f"Generated {date.today().isoformat()} from `{fixture.relative_to(ROOT)}`.",
        "",
        "Every check below is a rule the system prompt actually states, checked",
        "deterministically. No model judges another model.",
        "",
        "**The model score counts only answers the model actually wrote.** Every",
        "question it does not answer falls back to reviewed deterministic text,",
        "which passes every text rule by construction -- so a model that answers",
        "less would otherwise score higher. The coverage row is therefore part of",
        "the result, not a footnote: a high score on low coverage is mostly our",
        "pipeline's score.",
        "",
        "## Model quality",
        "",
    ]

    if not good:
        lines.append("No model completed the run.")
        return "\n".join(lines)

    def cell(report: dict, key: str) -> str:
        passed = report["totals"].get(key, 0)
        possible = report["applicable"].get(key, 0)
        if not possible:
            return "n/a"
        return f"{passed}/{possible} ({100 * passed // possible}%)"

    header = "| Check | " + " | ".join(r["model"] for r in good) + " |"
    lines += [header, "|" + "---|" * (len(good) + 1)]
    for key in MODEL_CHECKS:
        lines.append(
            f"| {CHECK_LABELS[key]} | "
            + " | ".join(cell(r, key) for r in good)
            + " |"
        )

    overall = []
    for report in good:
        passed = sum(report["totals"].get(k, 0) for k in MODEL_CHECKS)
        possible = sum(report["applicable"].get(k, 0) for k in MODEL_CHECKS)
        overall.append(f"**{100 * passed // possible}%**" if possible else "n/a")
    lines.append("| **Model score** | " + " | ".join(overall) + " |")
    lines.append(
        "| **Coverage** (answered / asked) | "
        + " | ".join(
            f"**{r['generated']}/{r['rows']}** "
            f"({100 * r['generated'] // r['rows']}%)"
            for r in good
        )
        + " |"
    )

    lines += [
        "",
        "A model that answers everything and a model that answers half are not",
        "comparable on the score alone. Read both rows together.",
        "",
        "## Pipeline",
        "",
        "These describe the deterministic service, not the model, and are",
        "expected to be identical everywhere. They are reported so a regression",
        "in the pipeline is visible -- not added to any model's score.",
        "",
        "| Check | " + " | ".join(r["model"] for r in good) + " |",
        "|" + "---|" * (len(good) + 1),
    ]
    for key in PIPELINE_CHECKS:
        lines.append(
            f"| {CHECK_LABELS[key]} | "
            + " | ".join(cell(r, key) for r in good)
            + " |"
        )

    lines += ["", "## Latency", ""]
    if len({r.get("provider", "ollama") for r in good}) > 1:
        # Mixing a local model with a hosted one in one table is the point --
        # compliance is what is being compared. Latency is not comparable that
        # way and should not be read as if it were.
        lines += [
            "**Providers differ in this run, so these are NOT comparable.** A local",
            "figure is compute only; a hosted figure includes network round-trip and",
            "the provider's own queueing. Compare compliance across providers, and",
            "latency only within one.",
            "",
        ]
    else:
        lines += ["Warm, GPU-resident; model load excluded.", ""]
    lines += [
        "| Metric | " + " | ".join(r["model"] for r in good) + " |",
        "|" + "---|" * (len(good) + 1),
        "| Provider | "
        + " | ".join(r.get("provider", "ollama") for r in good)
        + " |",
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

    if pending:
        lines += [
            "## Incomplete",
            "",
            "This run was stopped before these models were scored:",
            "",
        ]
        lines += [f"- `{m}`" for m in pending]
        lines.append("")

    return "\n".join(lines)


def save(path: Path, reports: list[dict], fixture: Path, pending: list[str]) -> None:
    """Write the report as it stands.

    Called after EVERY model, not once at the end.  A twelve-model sweep against
    a slow hosted provider runs for over an hour, and the end-only version threw
    away every completed model when a run was stopped on the last one -- an hour
    of real requests, gone, including the per-check columns that only exist in
    the file.  Writing each time costs a few milliseconds against minutes per
    model.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(reports, fixture, pending), encoding="utf-8")


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
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default="ollama",
        help="default provider; a 'provider:model' prefix overrides it per model",
    )
    args = parser.parse_args()

    rows = load_rows(args.fixture)
    crosswalk = UnityScenarioCrosswalk()

    reports: list[dict] = []
    for index, model in enumerate(args.models):
        print(
            f"running {model} ({index + 1}/{len(args.models)}) "
            f"over {len(rows)} questions...",
            flush=True,
        )
        try:
            report = run_model(
                model, rows, crosswalk, args.load_timeout, args.provider
            )
        except KeyboardInterrupt:
            # Ctrl-C mid-model: keep every model already scored rather than
            # losing the run. The report says which ones never ran.
            save(args.report, reports, args.fixture, list(args.models[index:]))
            print(
                f"\ninterrupted; kept {len(reports)} model(s) in {args.report}",
                file=sys.stderr,
            )
            return 130
        if "error" in report:
            print(f"  FAILED: {report['error']}", file=sys.stderr)
        else:
            # Model checks only, matching the report's headline. Summing every
            # check would fold in the pipeline rows that pass for everyone.
            passed = sum(report["totals"].get(k, 0) for k in MODEL_CHECKS)
            possible = sum(report["applicable"].get(k, 0) for k in MODEL_CHECKS)
            score = f"{100 * passed // possible}%" if possible else "n/a"
            print(
                f"  model score {score}, "
                f"coverage {report['generated']}/{report['rows']}, "
                f"median {report['median_ms']} ms",
                flush=True,
            )
        reports.append(report)
        # Persist now. Killing the process between models must not cost the
        # models already paid for.
        save(args.report, reports, args.fixture, list(args.models[index + 1:]))

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
