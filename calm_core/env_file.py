"""Read `.env` from the repo root into the process environment.

Why this exists: the OpenRouter key used to live only in each developer's
Windows user environment, which meant a fresh clone ran with no key at all.
That failure is quiet rather than loud -- `RAGChatService` catches
`LLMUnavailable` and answers from reviewed deterministic text -- so a
collaborator sees a working assistant that silently never calls a model.  A
committed `.env` removes that setup step.

Two deliberate properties:

- **An existing environment variable always wins.**  `os.environ.setdefault`,
  not assignment.  A collaborator with their own key in their user environment
  must not have it overridden by the shared one in the file, and `CALM_*`
  settings passed by the Unity launcher must survive too.
- **A missing or malformed file is not an error.**  The server has to start
  without `.env` -- the key can equally come from the real environment -- so
  this returns quietly rather than raising.

No new dependency: `python-dotenv` would pull a package into a project whose
benchmark bundle deliberately runs with zero pip installs.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The repo root, one level up from this package.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Apply `.env` to `os.environ` and return what it actually set.

    The return value names only the keys this call introduced, so a caller can
    log "loaded N settings" without ever reading a value back out.
    """

    source = path or ENV_PATH
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    applied: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        # `export FOO=bar` is a common shape in a hand-edited file.
        if name.startswith("export "):
            name = name[len("export ") :].strip()
        value = value.strip().strip('"').strip("'")
        if not name or not value:
            continue
        if name in os.environ and os.environ[name] != "":
            continue
        os.environ[name] = value
        applied[name] = value
    return applied
