from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from calm_core.session_log import (
    ALLOWED_FIELDS,
    REVIEWED_FIELDS,
    PrivacyRuleError,
    SessionLog,
)


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "corpus" / "system_rules.json"


class PrivacyEnforcementTests(unittest.TestCase):
    """The reason this module exists: policy a mistake cannot bypass.

    The answer payload legitimately carries the learner's question and spoken
    transcript. If filtering happened at the call site, one forgotten line would
    write a child's words to disk. These tests hand the sink exactly what the
    project's deny list forbids and require that none of it survives.
    """

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "sessions.jsonl"
        self.log = SessionLog(path=self.path)

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_forbidden_fields_are_dropped_even_when_handed_in(self) -> None:
        written = self.log.record(
            {
                "task_id": "eq_home_6_dch",
                "completion_code": "OK",
                "question": "bakit hindi ko dapat galawin",
                "response_text": "Huwag galawin ang bagay.",
                "transcript": "bakit hindi ko dapat galawin",
                "child_name": "Juan",
            }
        )

        for forbidden in ("question", "response_text", "transcript", "child_name"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, written)

    def test_forbidden_values_never_reach_the_file(self) -> None:
        """Assert on the bytes, not only the dict the sink returned."""

        self.log.record(
            {
                "task_id": "eq_home_6_dch",
                "question": "bakit hindi ko dapat galawin",
                "child_name": "Juan",
            }
        )
        raw = self.path.read_text(encoding="utf-8")

        self.assertNotIn("bakit", raw)
        self.assertNotIn("Juan", raw)

    def test_an_unforeseen_field_is_dropped(self) -> None:
        """An allowlist, so a field nobody anticipated cannot slip through."""

        written = self.log.record(
            {"task_id": "eq_home_6_dch", "learner_gaze_recording": "..."}
        )

        self.assertNotIn("learner_gaze_recording", written)

    def test_the_allowlist_is_checked_against_the_reviewed_policy(self) -> None:
        """The config is the authority; the code must cover what it permits."""

        rules = json.loads(RULES.read_text(encoding="utf-8"))["privacy_rules"]
        self.assertLessEqual(
            set(rules["default_storage"]), set(REVIEWED_FIELDS.values())
        )

    def test_a_policy_the_code_cannot_honour_refuses_to_start(self) -> None:
        """Better to stop than to log under a rule nobody implemented."""

        with tempfile.TemporaryDirectory() as directory:
            drifted = Path(directory) / "system_rules.json"
            drifted.write_text(
                json.dumps(
                    {
                        "privacy_rules": {
                            "default_storage": ["random_session_id", "gaze_track"],
                            "do_not_store_by_default": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PrivacyRuleError, "gaze_track"):
                SessionLog(path=self.path, rules_path=drifted)


class WriteBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "nested" / "sessions.jsonl"
        self.log = SessionLog(path=self.path)

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_events_append_rather_than_truncate(self) -> None:
        for code in ("OK", "OUTSIDE_DISASTER_SCOPE", "NO_RELEVANT_EVIDENCE"):
            self.log.record({"task_id": "eq_home_6_dch", "completion_code": code})

        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            [json.loads(line)["completion_code"] for line in lines],
            ["OK", "OUTSIDE_DISASTER_SCOPE", "NO_RELEVANT_EVIDENCE"],
        )

    def test_a_write_failure_never_raises(self) -> None:
        """A full disk must not cost a child their safety instruction."""

        with patch.object(Path, "open", side_effect=OSError("disk full")):
            written = self.log.record({"task_id": "eq_home_6_dch"})

        self.assertIsNone(written)
        self.assertTrue(self.log.status["write_failed"])

    def test_a_missing_session_id_still_writes(self) -> None:
        """An anonymous event beats refusing a question over a missing id."""

        written = self.log.record(
            {"task_id": "eq_home_6_dch", "completion_code": "OK"}
        )

        self.assertIsNotNone(written)
        self.assertNotIn("client_session_id", written)

    def test_the_timestamp_comes_from_the_server(self) -> None:
        """A client-supplied time is the audited party stamping the record."""

        written = self.log.record(
            {"task_id": "eq_home_6_dch", "timestamp": "1999-01-01T00:00:00+08:00"}
        )

        self.assertNotEqual(written["timestamp"], "1999-01-01T00:00:00+08:00")
        self.assertIn("event_id", written)

    def test_disabled_log_writes_nothing(self) -> None:
        log = SessionLog(path=self.path, enabled=False)

        self.assertIsNone(log.record({"task_id": "eq_home_6_dch"}))
        self.assertFalse(self.path.exists())


class AllowlistShapeTests(unittest.TestCase):
    def test_status_discloses_extended_fields_awaiting_policy_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status = SessionLog(path=Path(directory) / "events.jsonl").status

        self.assertIn("decision_trace", status["beyond_reviewed_policy"])
        self.assertIn("input_mode", status["beyond_reviewed_policy"])

    def test_no_free_text_field_is_permitted(self) -> None:
        """A standing guard on the allowlist itself."""

        for forbidden in (
            "question",
            "response_text",
            "transcript",
            "child_name",
            "active_simulation_instruction",
        ):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, ALLOWED_FIELDS)


if __name__ == "__main__":
    unittest.main()
