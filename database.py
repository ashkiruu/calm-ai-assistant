"""Compatibility adapter over CALM's curated protocol-card repository.

Raw PDF ingestion was intentionally removed.  PDF pages are evidence inputs to
the offline corpus pipeline, never direct learner-facing RAG chunks.
"""

from __future__ import annotations

from calm_core.repository import ProtocolRepository


class CALMDatabase:
    """Legacy name retained for callers while returning only curated semantics."""

    def __init__(self, mode: str = "development") -> None:
        self.repository = ProtocolRepository(mode=mode)

    def ingest_pdf(self, file_path: str, hazard_type: str) -> None:
        raise RuntimeError(
            "Direct PDF ingestion is disabled. Add the source to the audit, "
            "derive protocol cards, review them, then rebuild retrieval units."
        )

    def query_context(
        self,
        hazard_type: str,
        query_text: str,
        n_results: int = 2,
        locale: str = "en-PH",
    ) -> str:
        if hazard_type not in {"fire", "earthquake", "typhoon"}:
            return ""
        candidates = self.repository.candidates(
            hazard=hazard_type,
            criticalities={"P2_EDUCATIONAL"},
        )
        ranked = self.repository.rank_educational(candidates, query_text)
        selected = ranked[: max(0, n_results)]
        return "\n".join(
            card["language_pack"][locale]["tts_text"] for card in selected
        )
