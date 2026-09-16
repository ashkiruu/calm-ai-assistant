"""Pack the smallest tree that can score a model, for upload to Colab.

The benchmark needs far less than the whole project: `calm_core` imports only
the standard library plus its own siblings, so a Colab run needs no `pip
install` at all.  What it does need is the curated corpus and the crosswalk,
because `RAGChatService` refuses to answer without grounding.

Packing an explicit include list rather than "everything except venv" is
deliberate.  The full tree is ~196 MB -- `outputs/` alone is 64 MB of generated
artefacts -- against ~10 MB for the parts that actually participate in scoring.
An exclude list silently grows whenever someone adds a new heavy folder; an
include list fails loudly instead, which is the failure you want.

    python scripts/make_colab_bundle.py

Writes `calm_bench_bundle.zip` next to the project, ready to drag into Colab.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "calm_bench_bundle.zip"

#: Everything the scoring path touches, and nothing else.
INCLUDE = (
    "calm_core",       # the service itself -- stdlib-only, so no deps to install
    "config",          # unity_scenario_crosswalk.v1.json + school profile
    "corpus",          # protocol cards, approval gate, privacy rules
    "scripts",         # benchmark_models.py and the validators
    "tests/fixtures",  # scope_eval.jsonl -- the 44 reviewed questions
)
SKIP_SUFFIXES = (".pyc", ".pyo")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def wanted(path: Path) -> bool:
    if path.suffix in SKIP_SUFFIXES:
        return False
    return not any(part in SKIP_DIRS for part in path.parts)


def build(out_path: Path) -> tuple[int, int]:
    files = 0
    written = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for entry in INCLUDE:
            source = ROOT / entry
            if not source.exists():
                raise SystemExit(f"missing from the project: {entry}")
            for path in sorted(source.rglob("*")):
                if not path.is_file() or not wanted(path):
                    continue
                bundle.write(path, path.relative_to(ROOT).as_posix())
                files += 1
                written += path.stat().st_size
    return files, written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    files, written = build(args.out)
    packed = args.out.stat().st_size
    print(f"packed {files} files ({written / 1e6:.1f} MB) -> {args.out}")
    print(f"zip is {packed / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
