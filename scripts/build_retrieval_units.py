"""Create sanitized multilingual retrieval units from canonical protocol cards."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS_PATH = ROOT / "corpus" / "protocol_cards.jsonl"
OUTPUT_DIR = ROOT / "corpus" / "retrieval"
REVIEW_OUTPUT = OUTPUT_DIR / "review_candidate_units.jsonl"
RUNTIME_OUTPUT = OUTPUT_DIR / "runtime_units.jsonl"
MANIFEST_OUTPUT = OUTPUT_DIR / "manifest.json"


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def unit_for(card: dict, locale: str) -> dict:
    localized = card["language_pack"][locale]
    semantics = card["approved_semantics"]
    classification = card["classification"]
    source_claims = card["provenance"]["source_claims"]
    embedding_parts = [
        card["title"],
        semantics["objective"],
        localized["short_command"],
        localized["instruction"],
    ]
    return {
        "retrieval_id": f'{card["protocol_id"]}:{locale}',
        "protocol_id": card["protocol_id"],
        "revision": card["revision"],
        "action_code": card["action_code"],
        "hazard": classification["hazard"],
        "settings": classification["settings"],
        "phase": classification["phase"],
        "actor_role": classification["actor_role"],
        "age_band": classification["age_band"],
        "locale": locale,
        "criticality": card["deterministic_safety"]["criticality"],
        "generation_mode": card["deterministic_safety"]["generation_mode"],
        "lifecycle_state": card["review"]["lifecycle_state"],
        "required_context": card["applicability"]["required_context"],
        "trigger_events": card["applicability"]["trigger_events"],
        "embedding_text": " ".join(part.strip() for part in embedding_parts if part.strip()),
        "response_text": localized["tts_text"],
        "prohibited_actions": semantics["prohibited_actions"],
        "blocked_action_codes": card["deterministic_safety"]["blocks_action_codes"],
        "source_refs": [
            {
                "source_id": claim["source_id"],
                "locator": claim["locator"],
                "pages": claim.get("pages", []),
            }
            for claim in source_claims
        ],
        "conflict_ids": card["provenance"]["conflict_ids"],
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")


def main() -> None:
    cards = read_jsonl(CARDS_PATH)
    review_units = [
        unit_for(card, locale)
        for card in cards
        for locale in ("en-PH", "fil-PH", "taglish-PH")
    ]
    runtime_units = [
        unit
        for unit in review_units
        if unit["lifecycle_state"] == "RUNTIME_APPROVED"
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(REVIEW_OUTPUT, review_units)
    write_jsonl(RUNTIME_OUTPUT, runtime_units)

    state_counts = Counter(unit["lifecycle_state"] for unit in review_units)
    manifest = {
        "schema_version": "1.0",
        "protocol_cards": len(cards),
        "review_candidate_units": len(review_units),
        "runtime_units": len(runtime_units),
        "locales": ["en-PH", "fil-PH", "taglish-PH"],
        "lifecycle_unit_counts": dict(sorted(state_counts.items())),
        "production_gate": (
            "runtime_units.jsonl contains only RUNTIME_APPROVED cards. "
            "It is intentionally empty until external approvals are recorded."
        ),
        "excluded_from_embedding_text": [
            "author and contributor names",
            "addresses and static contact numbers",
            "acknowledgements",
            "legal and navigation boilerplate",
            "raw PDF paragraphs",
            "adult-only operational instructions",
            "unresolved conflicting claims"
        ]
    }
    with MANIFEST_OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
