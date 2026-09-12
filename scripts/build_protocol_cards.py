"""Build full CALM protocol cards from the reviewed compact specifications."""

from __future__ import annotations

import csv
import json
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = ROOT / "corpus" / "card_specs"
OUTPUT = ROOT / "corpus" / "protocol_cards.jsonl"
COVERAGE_OUTPUT = ROOT / "corpus" / "reports" / "coverage_matrix.csv"
REVIEW_QUEUE_OUTPUT = ROOT / "corpus" / "reports" / "review_queue.csv"

HAZARD_APPROVALS = {
    "fire": ["BFP", "DepEd_or_local_DRRMO"],
    "earthquake": ["PHIVOLCS", "DepEd_or_local_DRRMO"],
    "typhoon": ["PAGASA", "DepEd_or_local_DRRMO"],
}
COMMON_APPROVALS = [
    "Grade_4_child_safety",
    "Filipino_Taglish_language",
    "VR_implementation",
]


def load_specs() -> list[dict]:
    specs: list[dict] = []
    for path in sorted(SPECS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, list):
            raise ValueError(f"{path} must contain a JSON array")
        specs.extend(data)
    return specs


def generation_mode(criticality: str) -> str:
    return {
        "P0_CRITICAL": "EXACT_APPROVED_TEXT",
        "P1_IMPORTANT": "CONSTRAINED_APPROVED_TEXT",
        "P2_EDUCATIONAL": "GROUNDED_EXPLANATION",
    }[criticality]


def expand(spec: dict) -> dict:
    language_pack = {}
    for locale in ("en-PH", "fil-PH", "taglish-PH"):
        localized = spec["language"][locale]
        language_pack[locale] = {
            "short_command": localized["short"],
            "instruction": localized["instruction"],
            "tts_text": f'{localized["short"]} {localized["instruction"]}'.strip(),
        }

    criticality = spec["criticality"]
    return {
        "protocol_id": spec["protocol_id"],
        "schema_version": "1.0",
        "revision": 1,
        "action_code": spec["action_code"],
        "title": spec["title"],
        "classification": {
            "hazard": spec["hazard"],
            "secondary_hazards": spec.get("secondary_hazards", []),
            "settings": spec["settings"],
            "phase": spec["phase"],
            "actor_role": "learner",
            "age_band": "grades_3_to_6",
            "jurisdiction": "PH",
        },
        "applicability": {
            "required_context": spec["required_context"],
            "excluded_context": spec.get("excluded_context", []),
            "trigger_events": spec["trigger_events"],
            "context_sources": spec.get(
                "context_sources", ["trusted_vr_state", "learner_question"]
            ),
            "clarification_if": spec.get("clarification_if", []),
        },
        "approved_semantics": {
            "objective": spec["objective"],
            "ordered_actions": spec["ordered_actions"],
            "prohibited_actions": spec.get("prohibited_actions", []),
            "adult_handoff": spec.get("adult_handoff", ""),
            "rationale": spec.get("rationale", ""),
        },
        "deterministic_safety": {
            "criticality": criticality,
            "hard_guard": criticality == "P0_CRITICAL",
            "priority": spec["priority"],
            "generation_mode": generation_mode(criticality),
            "safe_default": spec["safe_default"],
            "blocks_action_codes": spec.get("blocks_action_codes", []),
        },
        "language_pack": language_pack,
        "provenance": {
            "source_claims": spec["source_claims"],
            "conflict_ids": spec.get("conflict_ids", []),
        },
        "review": {
            "lifecycle_state": spec.get("lifecycle_state", "EVIDENCE_LINKED"),
            "required_approvals": HAZARD_APPROVALS[spec["hazard"]]
            + COMMON_APPROVALS,
            "completed_approvals": [],
            "review_notes": spec.get(
                "review_notes",
                "Corpus-engineering draft; blocked until required external reviews.",
            ),
        },
    }


def write_coverage(cards: list[dict]) -> None:
    COVERAGE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    keys = list(product(("fire", "earthquake", "typhoon"), ("home", "school", "outdoor"), ("before", "during", "after")))
    rows = []
    for hazard, setting, phase in keys:
        matching = [
            card
            for card in cards
            if card["classification"]["hazard"] == hazard
            and setting in card["classification"]["settings"]
            and card["classification"]["phase"] == phase
        ]
        rows.append(
            {
                "hazard": hazard,
                "setting": setting,
                "phase": phase,
                "card_count": len(matching),
                "protocol_ids": ";".join(
                    card["protocol_id"] for card in matching
                ),
                "has_source_gap": any(
                    card["review"]["lifecycle_state"] == "NEEDS_CURRENT_SOURCE"
                    for card in matching
                ),
            }
        )

    with COVERAGE_OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_review_queue(cards: list[dict]) -> None:
    rows = []
    for card in cards:
        rows.append(
            {
                "protocol_id": card["protocol_id"],
                "revision": card["revision"],
                "hazard": card["classification"]["hazard"],
                "settings": ";".join(card["classification"]["settings"]),
                "phase": card["classification"]["phase"],
                "criticality": card["deterministic_safety"]["criticality"],
                "action_code": card["action_code"],
                "lifecycle_state": card["review"]["lifecycle_state"],
                "required_approvals": ";".join(
                    card["review"]["required_approvals"]
                ),
                "source_refs": ";".join(
                    f'{claim["source_id"]}:{claim["locator"]}'
                    for claim in card["provenance"]["source_claims"]
                ),
                "conflict_ids": ";".join(card["provenance"]["conflict_ids"]),
                "domain_decision": "",
                "child_safety_decision": "",
                "language_decision": "",
                "vr_decision": "",
                "reviewer_names": "",
                "review_date": "",
                "review_notes": "",
            }
        )
    with REVIEW_QUEUE_OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    specs = load_specs()
    ids = [spec["protocol_id"] for spec in specs]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"Duplicate protocol IDs: {duplicates}")

    cards = sorted((expand(spec) for spec in specs), key=lambda card: card["protocol_id"])
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        for card in cards:
            stream.write(json.dumps(card, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
    write_coverage(cards)
    write_review_queue(cards)
    print(
        json.dumps(
            {
                "cards": len(cards),
                "output": OUTPUT.relative_to(ROOT).as_posix(),
                "coverage": COVERAGE_OUTPUT.relative_to(ROOT).as_posix(),
                "review_queue": REVIEW_QUEUE_OUTPUT.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
