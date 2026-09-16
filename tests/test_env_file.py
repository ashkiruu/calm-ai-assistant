"""`.env` loading, with the precedence rule pinned down.

The precedence is the part worth testing. If the file won over the real
environment, the shared committed key would silently override a collaborator's
own key, and the Unity launcher's CALM_* settings would stop taking effect --
both of which fail quietly rather than loudly.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from calm_core.env_file import ENV_PATH, load_env_file


class EnvFileTests(unittest.TestCase):
    def write(self, body: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".env", delete=False, encoding="utf-8"
        )
        handle.write(body)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_it_sets_a_variable_that_is_not_already_present(self) -> None:
        path = self.write("CALM_TEST_TOKEN=from-file\n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CALM_TEST_TOKEN", None)
            applied = load_env_file(path)

            self.assertEqual(applied, {"CALM_TEST_TOKEN": "from-file"})

    def test_a_real_environment_variable_wins(self) -> None:
        """The whole point: a collaborator's own key must not be overridden."""

        path = self.write("CALM_TEST_TOKEN=from-file\n")
        with patch.dict(os.environ, {"CALM_TEST_TOKEN": "from-shell"}):
            applied = load_env_file(path)

            self.assertEqual(applied, {})
            self.assertEqual(os.environ["CALM_TEST_TOKEN"], "from-shell")

    def test_an_empty_environment_variable_does_not_win(self) -> None:
        """An exported-but-blank variable is absence, not a deliberate choice."""

        path = self.write("CALM_TEST_TOKEN=from-file\n")
        with patch.dict(os.environ, {"CALM_TEST_TOKEN": ""}):
            load_env_file(path)

            self.assertEqual(os.environ["CALM_TEST_TOKEN"], "from-file")

    def test_comments_blanks_quotes_and_export_are_handled(self) -> None:
        path = self.write(
            "# a comment\n"
            "\n"
            "   \n"
            'CALM_TEST_QUOTED="quoted value"\n'
            "export CALM_TEST_EXPORTED=exported\n"
            "CALM_TEST_NOEQUALS\n"
            "CALM_TEST_EMPTY=\n"
        )
        with patch.dict(os.environ, {}, clear=False):
            for name in (
                "CALM_TEST_QUOTED",
                "CALM_TEST_EXPORTED",
                "CALM_TEST_NOEQUALS",
                "CALM_TEST_EMPTY",
            ):
                os.environ.pop(name, None)
            applied = load_env_file(path)

        self.assertEqual(applied["CALM_TEST_QUOTED"], "quoted value")
        self.assertEqual(applied["CALM_TEST_EXPORTED"], "exported")
        self.assertNotIn("CALM_TEST_NOEQUALS", applied)
        self.assertNotIn("CALM_TEST_EMPTY", applied)

    def test_a_missing_file_is_quiet(self) -> None:
        """The server must start with no .env -- the key can come from the shell."""

        self.assertEqual(load_env_file(Path("no-such-file-here.env")), {})

    def test_the_committed_env_supplies_a_key_and_the_benchmarked_model(self) -> None:
        """Guards the thing a fresh clone depends on.

        Asserts the key is present and non-placeholder without reading its
        value into the test output.
        """

        if not ENV_PATH.exists():
            self.skipTest(".env is not present in this checkout")

        settings = {}
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                name, _, value = line.partition("=")
                settings[name.strip()] = value.strip()

        self.assertIn("OPENROUTER_API_KEY", settings)
        self.assertTrue(settings["OPENROUTER_API_KEY"].startswith("sk-or-"))
        self.assertNotIn("your-key-here", settings["OPENROUTER_API_KEY"])
        self.assertEqual(settings["CALM_LLM_PROVIDER"], "openrouter")
        self.assertEqual(
            settings["CALM_OPENROUTER_MODEL"], "deepseek/deepseek-v4-flash"
        )


if __name__ == "__main__":
    unittest.main()
