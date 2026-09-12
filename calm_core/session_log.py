"""Append privacy-safe session events for evaluation and audit.

The project already states what may be stored: ``privacy_rules`` in
``corpus/system_rules.json`` carries a ``default_storage`` allowlist and a
``do_not_store_by_default`` deny list.  Until now nothing read it, so the rule
lived only in prose and in one unit test.  This module makes it mechanical: a
key not on the allowlist never reaches the file, whatever the caller passes.

That direction matters.  The answer payload legitimately contains the learner's
question and the spoken transcript, so a sink that filtered at the call site
would be one forgotten line away from writing a child's words to disk.
Filtering here means the mistake cannot be made upstream.

Writes are best effort by design.  A learner waiting for a safety instruction
must never wait on a log, and must never lose the answer because a disk filled.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "corpus" / "system_rules.json"
DEFAULT_LOG = ROOT / "logs" / "sessions.jsonl"

#: Concrete event keys, each carrying one concept from the reviewed
#: ``default_storage`` list.  The policy names concepts rather than field names,
#: so the mapping is stated here and checked against the config at construction:
#: if the reviewed policy changes, the code refuses to start rather than quietly
#: logging under a stale rule.
REVIEWED_FIELDS = {
    "client_session_id": "random_session_id",
    "event_id": "random_session_id",
    "state_id": "vr_state_id",
    "task_id": "vr_state_id",
    "scenario_id": "vr_state_id",
    "protocol_id": "protocol_id",
    "protocol_ids": "protocol_id",
    "timestamp": "timestamp",
    "latency_ms": "latency_ms",
    "completion_code": "completion_or_error_code",
}

#: Decision metadata the RAG path produces that the reviewed list predates.
#: None of it identifies a learner: it is which branch answered, from which
#: hazard's evidence, in which language, and whether a model was involved.
#: Recorded so the scope gate can be evaluated at all, and listed separately so
#: the next corpus review can see exactly what was added and rule on it.
EXTENDED_FIELDS = {
    "answer_source",
    "asked_hazard",
    "decision_trace",
    "deferred_question",
    "endpoint",
    "evidence_scope",
    "hazard",
    "input_mode",
    "llm_used",
    "locale",
    "mapping_status",
    "model",
    "phase",
    "prompt_policy_version",
    "question_scope",
    "setting",
}

# These fields are intentionally useful for prototype evaluation but are not
# named by privacy_rules.default_storage yet. Expose that gap truthfully in
# /health so "beyond_reviewed_policy" cannot report an empty list while the
# sink is accepting additional telemetry.
UNREVIEWED_EXTENDED_CONCEPTS = tuple(sorted(EXTENDED_FIELDS))

ALLOWED_FIELDS = frozenset(REVIEWED_FIELDS) | EXTENDED_FIELDS


class PrivacyRuleError(RuntimeError):
    """Raised when the reviewed policy and this module have drifted apart."""


def _load_rules(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)["privacy_rules"]


class SessionLog:
    """Append-only sink for sanitized events.

    Never read back at runtime: nothing about answering a question depends on
    what is already in the file.
    """

    def __init__(
        self,
        path: Path | None = None,
        rules_path: Path | None = None,
        enabled: bool = True,
    ) -> None:
        self.path = Path(path or os.getenv("CALM_SESSION_LOG", DEFAULT_LOG))
        self.enabled = enabled
        self._lock = threading.Lock()
        self._failed = False

        rules = _load_rules(rules_path or DEFAULT_RULES)
        self.denied_concepts = tuple(rules.get("do_not_store_by_default", ()))

        covered = set(REVIEWED_FIELDS.values())
        reviewed = set(rules.get("default_storage", ()))
        missing = reviewed - covered
        if missing:
            # The policy permits something this module has no field for. That is
            # a review decision that has not reached the code, so stop rather
            # than log under an assumption about what was intended.
            raise PrivacyRuleError(
                "privacy_rules.default_storage permits concepts this log does "
                f"not carry: {sorted(missing)}"
            )
        self.extra_concepts = tuple(sorted(covered - reviewed))

    @property
    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "allowed_field_count": len(ALLOWED_FIELDS),
            "beyond_reviewed_policy": sorted(
                {*self.extra_concepts, *UNREVIEWED_EXTENDED_CONCEPTS}
            ),
            "write_failed": self._failed,
        }

    @staticmethod
    def new_event_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _timestamp() -> str:
        """Server clock, always.

        The router accepts a client-supplied timestamp, which is fine for
        correlation but not for an audit trail: the record's own time would
        otherwise come from the party being audited.
        """

        return datetime.now(timezone.utc).astimezone().isoformat()

    def sanitize(self, event: dict[str, Any]) -> dict[str, Any]:
        """Drop every key that is not explicitly permitted.

        An allowlist rather than a deny list, because the risk is a field nobody
        thought about: a deny list only catches what was foreseen.
        """

        return {
            key: value
            for key, value in event.items()
            if key in ALLOWED_FIELDS and value is not None
        }

    def record(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Sanitize, stamp, and append one event. Returns what was written."""

        if not self.enabled:
            return None

        entry = self.sanitize(event)
        entry["event_id"] = self.new_event_id()
        entry["timestamp"] = self._timestamp()

        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # A full disk, a locked file, a read-only volume. None is a reason
            # to fail a child's safety question, so the answer wins and the loss
            # shows up in status rather than as an exception.
            self._failed = True
            return None
        return entry


__all__ = [
    "ALLOWED_FIELDS",
    "DEFAULT_LOG",
    "EXTENDED_FIELDS",
    "REVIEWED_FIELDS",
    "PrivacyRuleError",
    "SessionLog",
]
