"""Validate Unity mission coverage and curated protocol-card grounding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calm_core.unity_crosswalk import DEFAULT_CARDS, DEFAULT_CROSSWALK, validate_crosswalk


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument(
        "--unity-library",
        type=Path,
        help="Optional path to MissionLibrary.cs; the configured path is used when present.",
    )
    args = parser.parse_args()
    report = validate_crosswalk(args.crosswalk, args.cards, args.unity_library)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
