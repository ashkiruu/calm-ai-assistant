"""Summarize recorded sessions into a report.

The model benchmark measures the assistant against a reviewed question set.
This measures what actually happened when children used it: which tasks provoked
questions, how often the scope gate deferred or refused, and whether it was fast
enough to be worth speaking to.

Reads only what the session log wrote, and the log cannot contain a learner's
words, so neither can this.

    python scripts/session_report.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calm_core.session_log import DEFAULT_LOG

DEFAULT_REPORT = ROOT / "docs" / "SESSION_REPORT.md"

#: Codes where the learner asked something the assistant chose not to answer
#: from the model. Grouped because "how often did it decline, and why" is the
#: question a reviewer asks first.
DECLINED = {
    "DEFERRED_DURING_CRITICAL_TASK",
    "OUTSIDE_DISASTER_SCOPE",
    "NO_RELEVANT_EVIDENCE",
}


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # A truncated final line is what a killed process leaves behind.
                # One unreadable row should not cost the whole report.
                continue
    return events


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(int(len(ordered) * fraction), len(ordered) - 1)
    return ordered[index]


def _table(title: str, counts: Counter, total: int) -> list[str]:
    lines = [f"### {title}", "", "| Value | Count | Share |", "|---|---|---|"]
    for value, count in counts.most_common():
        share = f"{100 * count // total}%" if total else "-"
        lines.append(f"| `{value}` | {count} | {share} |")
    lines.append("")
    return lines


def render(events: list[dict], source: Path) -> str:
    shown = source.relative_to(ROOT) if source.is_relative_to(ROOT) else source
    lines = [
        "# Session report",
        "",
        f"Generated {date.today().isoformat()} from `{shown}`.",
        "",
    ]

    if not events:
        lines += ["No events recorded yet. Run a session and ask a question.", ""]
        return "\n".join(lines)

    sessions = {
        event.get("client_session_id")
        for event in events
        if event.get("client_session_id")
    }
    anonymous = sum(1 for event in events if not event.get("client_session_id"))
    generated = [event for event in events if event.get("llm_used")]
    declined = [
        event for event in events if event.get("completion_code") in DECLINED
    ]
    latencies = [
        int(event["latency_ms"])
        for event in events
        if isinstance(event.get("latency_ms"), (int, float))
        and event.get("llm_used")
    ]

    lines += [
        "## Overview",
        "",
        "| | |",
        "|---|---|",
        f"| Questions answered | {len(events)} |",
        f"| Sessions | {len(sessions)} |",
        f"| Answered by the model | {len(generated)} |",
        f"| Answered from reviewed text | {len(events) - len(generated)} |",
        f"| Declined to answer from the model | {len(declined)} "
        f"({100 * len(declined) // len(events)}%) |",
        "",
    ]
    if anonymous:
        lines += [
            f"{anonymous} event(s) carry no session id and are counted but not "
            "grouped.",
            "",
        ]

    lines += ["## Decisions", ""]
    lines += _table(
        "Question scope",
        Counter(event.get("question_scope", "unknown") for event in events),
        len(events),
    )
    lines += _table(
        "Completion code",
        Counter(event.get("completion_code", "unknown") for event in events),
        len(events),
    )
    lines += _table(
        "Language answered in",
        Counter(event.get("locale", "unknown") for event in events),
        len(events),
    )

    lines += ["## Latency", ""]
    if latencies:
        lines += [
            "Generated answers only. A reviewed reply involves no model and "
            "returns in well under a millisecond, so including those would "
            "flatter the figure.",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Median | {int(statistics.median(latencies))} ms |",
            f"| p90 | {_percentile(latencies, 0.9)} ms |",
            f"| Slowest | {max(latencies)} ms |",
            "",
        ]
    else:
        lines += ["No generated answers recorded.", ""]

    tasks = Counter(event.get("task_id", "unknown") for event in events)
    lines += ["## Most-questioned tasks", "", "| Task | Questions |", "|---|---|"]
    for task_id, count in tasks.most_common(10):
        lines.append(f"| `{task_id}` | {count} |")
    lines.append("")

    deferrals = Counter(
        event.get("task_id", "unknown")
        for event in events
        if event.get("completion_code") == "DEFERRED_DURING_CRITICAL_TASK"
    )
    if deferrals:
        lines += [
            "## Where curiosity met a live hazard",
            "",
            "Tasks where a child asked about a different emergency while one was "
            "happening. These are the moments the scope gate exists for, and are "
            "worth reading alongside the lesson design.",
            "",
            "| Task | Deferrals |",
            "|---|---|",
        ]
        for task_id, count in deferrals.most_common(10):
            lines.append(f"| `{task_id}` | {count} |")
        lines.append("")

    lines += [
        "## Privacy",
        "",
        "Every field here comes from the session log, whose allowlist is checked "
        "against `privacy_rules` in `corpus/system_rules.json`. No learner "
        "question, answer text, or transcript is recorded, so none can appear in "
        "this report.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    events = load(args.log)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render(events, args.log), encoding="utf-8")

    print(f"read {len(events)} event(s) from {args.log}")
    if events:
        codes = Counter(event.get("completion_code", "unknown") for event in events)
        for code, count in codes.most_common():
            print(f"  {code}: {count}")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
