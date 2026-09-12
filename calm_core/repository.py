"""Load only curated CALM protocol cards that pass the selected corpus gate."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARDS = ROOT / "corpus" / "protocol_cards.jsonl"
DEFAULT_DEVELOPMENT_GATE = ROOT / "corpus" / "development_approval.json"

PRODUCTION_STATE = "RUNTIME_APPROVED"
SUPPORTED_MODES = {"development", "production"}

_STOPWORDS = {
    "a", "about", "ako", "ang", "ano", "at", "ay", "ba", "do", "for",
    "how", "i", "in", "is", "it", "ko", "kung", "mga", "my", "ng", "on",
    "or", "sa", "should", "the", "to", "what", "when", "where", "why",
    "with", "you", "your",
}


class CorpusGateError(RuntimeError):
    """Raised when corpus metadata would permit an unsafe runtime state."""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise CorpusGateError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CorpusGateError(
                    f"{path.name}:{line_number} must contain an object"
                )
            records.append(value)
    return records


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    words = re.findall(r"[a-z0-9]+", normalized)
    return {word for word in words if len(word) > 1 and word not in _STOPWORDS}


def content_tokens(value: str) -> set[str]:
    """Public tokenizer so callers can score text against curated content."""

    return _tokens(value)


class ProtocolRepository:
    """Read curated cards and enforce development or production eligibility."""

    def __init__(
        self,
        cards_path: Path | None = None,
        development_gate_path: Path | None = None,
        mode: str = "development",
    ) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in SUPPORTED_MODES:
            raise CorpusGateError(
                f"Unsupported corpus mode {mode!r}; use development or production"
            )

        self.mode = normalized_mode
        self.cards_path = cards_path or DEFAULT_CARDS
        self.development_gate_path = (
            development_gate_path or DEFAULT_DEVELOPMENT_GATE
        )
        self.development_gate = _read_json(self.development_gate_path)
        self._all_cards = _read_jsonl(self.cards_path)
        self._validate_gate()
        self._cards = [card for card in self._all_cards if self._eligible(card)]
        self._by_id = {card["protocol_id"]: card for card in self._cards}

    def _validate_gate(self) -> None:
        if (
            self.development_gate.get("decision")
            != "INTERNAL_DEVELOPMENT_VALIDATED"
        ):
            raise CorpusGateError("Development corpus gate is missing or invalid")
        allowed = set(
            self.development_gate.get("eligible_lifecycle_states", [])
        )
        excluded = set(
            self.development_gate.get("excluded_lifecycle_states", [])
        )
        if PRODUCTION_STATE in allowed:
            raise CorpusGateError(
                "The internal development decision must not grant production approval"
            )
        if allowed & excluded:
            raise CorpusGateError("Corpus gate allows and excludes the same state")

    def _eligible(self, card: dict[str, Any]) -> bool:
        state = card.get("review", {}).get("lifecycle_state")
        if self.mode == "production":
            return state == PRODUCTION_STATE
        return state in set(
            self.development_gate["eligible_lifecycle_states"]
        )

    @property
    def cards(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._cards)

    @property
    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "decision": (
                self.development_gate["decision"]
                if self.mode == "development"
                else "EXTERNAL_RUNTIME_GATE"
            ),
            "eligible_card_count": len(self._cards),
            "total_card_count": len(self._all_cards),
            "runtime_approved": self.mode == "production" and bool(self._cards),
            "real_emergency_use": False,
        }

    def get(self, protocol_id: str) -> dict[str, Any] | None:
        return self._by_id.get(protocol_id)

    def candidates(
        self,
        *,
        hazard: str | None = None,
        phase: str | None = None,
        setting: str | None = None,
        criticalities: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        criticality_set = set(criticalities or [])
        result: list[dict[str, Any]] = []
        for card in self._cards:
            classification = card["classification"]
            if hazard and classification["hazard"] != hazard:
                continue
            if phase and classification["phase"] != phase:
                continue
            if setting and setting not in classification["settings"]:
                continue
            if (
                criticality_set
                and card["deterministic_safety"]["criticality"]
                not in criticality_set
            ):
                continue
            result.append(card)
        return result

    def rank_educational_scored(
        self,
        cards: Iterable[dict[str, Any]],
        question: str,
        locale: str | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        """Rank curated cards and expose the overlap score with each one.

        The score lets a caller refuse to answer at all.  Ranking alone never
        expresses relevance: a question sharing no words with any card still
        produces a full ordering, so a caller that blindly takes the first
        result answers off-topic questions with the highest-priority card.
        Passing a locale also searches that locale's reviewed language pack.
        Raw PDF text is never searched.
        """

        query_tokens = _tokens(question)
        scored: list[tuple[int, int, str, dict[str, Any]]] = []
        for card in cards:
            parts = [
                card["title"],
                card["action_code"].replace("_", " "),
                card["approved_semantics"]["objective"],
                *card["approved_semantics"]["ordered_actions"],
            ]
            if locale:
                # Card prose is English, so a Filipino or Taglish question scores
                # zero against it and a real safety question looks irrelevant.
                # The reviewed language pack carries the same content translated.
                localized = card["language_pack"][locale]
                parts.extend(
                    [localized["short_command"], localized["instruction"]]
                )
            searchable = " ".join(parts)
            overlap = len(query_tokens & _tokens(searchable))
            priority = int(card["deterministic_safety"].get("priority", 0))
            scored.append((overlap, priority, card["protocol_id"], card))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [(item[0], item[3]) for item in scored]

    def rank_educational(
        self,
        cards: Iterable[dict[str, Any]],
        question: str,
    ) -> list[dict[str, Any]]:
        """Rank already-filtered curated cards; raw PDF text is never searched."""

        return [card for _, card in self.rank_educational_scored(cards, question)]
