"""Extract a page-traceable raw corpus from CALM source PDFs.

This script intentionally does not decide whether a passage is safe or suitable
for learners. It creates the immutable extraction layer used by the later human
corpus audit and protocol-card build.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RUN = re.compile(r"[ \t]+")
SOURCE_ID_CHARS = re.compile(r"[^a-z0-9]+")


def source_id_for(path: Path) -> str:
    stem = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode()
    source_id = SOURCE_ID_CHARS.sub("-", stem.lower()).strip("-")
    return source_id or hashlib.sha256(path.name.encode()).hexdigest()[:12]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_line(line: str) -> str:
    line = unicodedata.normalize("NFKC", line)
    line = CONTROL_CHARS.sub("", line)
    return SPACE_RUN.sub(" ", line).strip()


def extract_page_lines(page: fitz.Page, use_ocr: bool) -> tuple[list[str], str]:
    blocks = page.get_text("blocks", sort=True)
    lines: list[str] = []
    for block in blocks:
        for raw_line in str(block[4]).splitlines():
            line = normalize_line(raw_line)
            if line:
                lines.append(line)

    extraction_method = "native"
    visible_chars = sum(len(line) for line in lines)
    if use_ocr and visible_chars < 40:
        try:
            text_page = page.get_textpage_ocr(language="eng", dpi=200, full=True)
            ocr_lines = [
                normalize_line(line)
                for line in page.get_text("text", textpage=text_page, sort=True).splitlines()
            ]
            ocr_lines = [line for line in ocr_lines if line]
            if sum(len(line) for line in ocr_lines) > visible_chars:
                lines = ocr_lines
                extraction_method = "ocr"
        except Exception as exc:  # The audit records the failure for manual review.
            extraction_method = f"ocr_failed:{type(exc).__name__}"

    return lines, extraction_method


def repeated_line_keys(pages: list[dict]) -> set[str]:
    page_count = len(pages)
    if page_count < 4:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        unique = {
            normalize_line(line).casefold()
            for line in page["lines"]
            if 2 <= len(normalize_line(line)) <= 180
        }
        counts.update(unique)

    threshold = max(3, round(page_count * 0.20))
    return {line for line, count in counts.items() if count >= threshold}


def extract_pdf(path: Path, output_dir: Path, use_ocr: bool) -> dict:
    document = fitz.open(path)
    pages: list[dict] = []

    for page_index, page in enumerate(document):
        lines, method = extract_page_lines(page, use_ocr=use_ocr)
        pages.append(
            {
                "page": page_index + 1,
                "extraction_method": method,
                "line_count": len(lines),
                "character_count": sum(len(line) for line in lines),
                "lines": lines,
            }
        )

    boilerplate = repeated_line_keys(pages)
    source_id = source_id_for(path)
    raw_path = output_dir / f"{source_id}.jsonl"

    with raw_path.open("w", encoding="utf-8", newline="\n") as stream:
        for page in pages:
            page_lines = []
            for line_number, text in enumerate(page["lines"], start=1):
                page_lines.append(
                    {
                        "line": line_number,
                        "text": text,
                        "is_repeated_boilerplate": text.casefold() in boilerplate,
                    }
                )
            record = {
                "source_id": source_id,
                "file_name": path.name,
                "page": page["page"],
                "extraction_method": page["extraction_method"],
                "line_count": page["line_count"],
                "character_count": page["character_count"],
                "lines": page_lines,
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    metadata = document.metadata or {}
    document.close()
    return {
        "source_id": source_id,
        "file_name": path.name,
        "file_path": path.as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "pages": len(pages),
        "pdf_title": normalize_line(metadata.get("title") or ""),
        "native_pages": sum(p["extraction_method"] == "native" for p in pages),
        "ocr_pages": sum(p["extraction_method"] == "ocr" for p in pages),
        "ocr_failed_pages": sum(
            str(p["extraction_method"]).startswith("ocr_failed") for p in pages
        ),
        "low_text_pages": sum(p["character_count"] < 40 for p in pages),
        "raw_jsonl": raw_path.as_posix(),
    }


def write_registry(records: list[dict], registry_path: Path) -> None:
    hash_owner: dict[str, str] = {}
    for record in records:
        record["duplicate_of"] = hash_owner.get(record["sha256"], "")
        hash_owner.setdefault(record["sha256"], record["source_id"])

    fields = [
        "source_id",
        "file_name",
        "file_path",
        "sha256",
        "bytes",
        "pages",
        "pdf_title",
        "native_pages",
        "ocr_pages",
        "ocr_failed_pages",
        "low_text_pages",
        "duplicate_of",
        "raw_jsonl",
        "issuing_authority",
        "publication_year",
        "authority_tier",
        "hazard_scope",
        "audience",
        "language",
        "corpus_status",
        "review_status",
        "source_url",
        "notes",
    ]

    with registry_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **record,
                    "issuing_authority": "",
                    "publication_year": "",
                    "authority_tier": "",
                    "hazard_scope": "",
                    "audience": "",
                    "language": "",
                    "corpus_status": "PENDING_AUDIT",
                    "review_status": "PENDING",
                    "source_url": "",
                    "notes": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("documents"))
    parser.add_argument("--output", type=Path, default=Path("corpus/raw_pages"))
    parser.add_argument(
        "--registry", type=Path, default=Path("corpus/pdf_inventory.csv")
    )
    parser.add_argument(
        "--ocr-low-text",
        action="store_true",
        help="OCR pages with fewer than 40 native text characters.",
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="Process only this PDF filename. May be supplied more than once.",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.registry.parent.mkdir(parents=True, exist_ok=True)

    if args.files:
        pdf_paths = [args.input / file_name for file_name in args.files]
        missing = [path for path in pdf_paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Requested PDF files not found: "
                + ", ".join(path.as_posix() for path in missing)
            )
    else:
        pdf_paths = list(args.input.rglob("*.pdf"))
    pdf_paths = sorted(pdf_paths, key=lambda path: path.as_posix().casefold())
    records = [
        extract_pdf(path, output_dir=args.output, use_ocr=args.ocr_low_text)
        for path in pdf_paths
    ]
    write_registry(records, args.registry)

    print(
        json.dumps(
            {
                "documents": len(records),
                "pages": sum(record["pages"] for record in records),
                "ocr_pages": sum(record["ocr_pages"] for record in records),
                "ocr_failed_pages": sum(
                    record["ocr_failed_pages"] for record in records
                ),
                "low_text_pages": sum(record["low_text_pages"] for record in records),
                "registry": args.registry.as_posix(),
                "raw_output": args.output.as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
