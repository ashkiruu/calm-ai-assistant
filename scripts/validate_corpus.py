"""Validate CALM Phase 1 corpus integrity, safety gates, and context coverage."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from itertools import product
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
REPORT_PATH = CORPUS / "reports" / "validation_report.json"

REQUIRED_CARD_FIELDS = {
    "protocol_id",
    "schema_version",
    "revision",
    "action_code",
    "title",
    "classification",
    "applicability",
    "approved_semantics",
    "deterministic_safety",
    "language_pack",
    "provenance",
    "review",
}
LOCALES = {"en-PH", "fil-PH", "taglish-PH"}
HAZARDS = {"fire", "earthquake", "typhoon"}
SETTINGS = {"home", "school", "outdoor"}
PHASES = {"before", "during", "after"}
BLOCKED_RUNTIME_STATES = {
    "DRAFT",
    "EVIDENCE_LINKED",
    "ROLE_CONTEXT_CLASSIFIED",
    "DOMAIN_APPROVED",
    "CHILD_SAFETY_APPROVED",
    "LANGUAGE_EQUIVALENCE_APPROVED",
    "VR_RULE_TESTED",
    "PILOT_APPROVED",
    "CONFLICT_HOLD",
    "NEEDS_CURRENT_SOURCE",
    "SUSPENDED",
    "SUPERSEDED",
    "RETIRED",
}
UNSAFE_ORDERED_ACTION_PATTERNS = {
    "child fire suppression": re.compile(
        r"\b(fight|extinguish|put out)\b.{0,30}\bfire\b|\buse\b.{0,20}\bextinguisher\b",
        re.IGNORECASE,
    ),
    "child utility operation": re.compile(
        r"\b(turn|switch|shut|close|open|operate)\b.{0,35}\b("
        r"breaker|main switch|electricity|gas|lpg|valve)\b",
        re.IGNORECASE,
    ),
    "child flood entry": re.compile(
        r"\b(walk|wade|swim|enter|cross|drive|boat)\b.{0,25}\bfloodwater\b",
        re.IGNORECASE,
    ),
    "child rescue": re.compile(
        r"\b(rescue|carry)\b.{0,35}\b(person|people|someone|pet)\b",
        re.IGNORECASE,
    ),
    "child medication": re.compile(
        r"\b(give|take|apply)\b.{0,25}\b(medicine|medication)\b",
        re.IGNORECASE,
    ),
}
QUARANTINED_SOURCE_PAGES = {
    "volume-1-fire-safety-for-children": {
        202,
        243,
        284,
        296,
        304,
        322,
        323,
        324,
        325,
    }
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{line_number}: invalid JSON: {exc}")
                continue
            if not isinstance(value, dict):
                errors.append(f"{path.name}:{line_number}: record is not an object")
                continue
            records.append(value)
    return records


def validate_sources(errors: list[str], warnings: list[str]) -> dict[str, dict]:
    with (CORPUS / "source_registry.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    source_ids: dict[str, dict] = {}
    active_hashes: dict[str, str] = {}
    for row in rows:
        source_id = row["source_id"]
        if source_id in source_ids:
            errors.append(f"Duplicate source_id: {source_id}")
        source_ids[source_id] = row

        if row["source_type"] != "pdf":
            if not row["source_url"]:
                warnings.append(f"Web source lacks URL: {source_id}")
            continue

        path = ROOT / row["relative_path"]
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"Missing PDF for {source_id}: {row['relative_path']}")
            continue
        if ROOT.resolve() not in resolved.parents:
            errors.append(f"PDF escaped workspace: {resolved}")
            continue
        if sha256_file(resolved) != row["sha256"]:
            errors.append(f"SHA-256 mismatch: {source_id}")
        if resolved.stat().st_size != int(row["bytes"]):
            errors.append(f"Byte-size mismatch: {source_id}")
        with fitz.open(resolved) as document:
            if len(document) != int(row["pages"]):
                errors.append(f"Page-count mismatch: {source_id}")

        if row["corpus_status"].startswith(("APPROVED", "REFERENCE")):
            other = active_hashes.get(row["sha256"])
            if other:
                errors.append(
                    f"Exact duplicate remains in approved/reference sources: "
                    f"{other} and {source_id}"
                )
            active_hashes[row["sha256"]] = source_id

    root_pdfs = list((ROOT / "documents").glob("*.pdf"))
    incoming_pdfs = list((ROOT / "documents" / "incoming").glob("*.pdf"))
    if root_pdfs:
        errors.append("Unclassified PDFs remain at documents root")
    if incoming_pdfs:
        errors.append("Unaudited PDFs remain in documents/incoming")
    return source_ids


def validate_pdf_derivation_matrix(
    sources: dict[str, dict], errors: list[str]
) -> dict:
    path = CORPUS / "reports" / "pdf_derivation_matrix.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    expected_ids = {
        source_id
        for source_id, source in sources.items()
        if source["source_type"] == "pdf"
    }
    ids = [row.get("source_id", "") for row in rows]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Duplicate PDF derivation rows: {duplicates}")

    actual_ids = set(ids)
    if expected_ids - actual_ids:
        errors.append(
            "PDF derivation matrix is missing sources: "
            f"{sorted(expected_ids - actual_ids)}"
        )
    if actual_ids - expected_ids:
        errors.append(
            "PDF derivation matrix has unknown/non-PDF sources: "
            f"{sorted(actual_ids - expected_ids)}"
        )

    valid_storage = {"approved", "reference", "archive"}
    valid_decisions = {
        "CURATED_DERIVATION",
        "NONRUNTIME_REFERENCE",
        "BACKGROUND_ONLY",
        "EXCLUDE",
        "DUPLICATE",
    }
    for row in rows:
        source_id = row.get("source_id", "<missing>")
        storage = row.get("recommended_storage", "")
        if storage not in valid_storage:
            errors.append(f"{source_id}: invalid recommended storage {storage}")
        if row.get("direct_pdf_rag") != "NO":
            errors.append(f"{source_id}: raw PDF must not be direct learner RAG")
        if row.get("derivation_decision") not in valid_decisions:
            errors.append(f"{source_id}: invalid derivation decision")
        if not row.get("active_evidence_layers", "").strip():
            errors.append(f"{source_id}: no evidence-layer decision")

        source = sources.get(source_id)
        if not source:
            continue
        status_prefix = {
            "approved": "APPROVED",
            "reference": "REFERENCE",
            "archive": "ARCHIVED",
        }.get(storage)
        if status_prefix and not source["corpus_status"].startswith(status_prefix):
            errors.append(
                f"{source_id}: matrix storage {storage} disagrees with "
                f"registry status {source['corpus_status']}"
            )

    return {
        "audited_pdf_count": len(rows),
        "approved_pdf_count": sum(
            row.get("recommended_storage") == "approved" for row in rows
        ),
        "reference_pdf_count": sum(
            row.get("recommended_storage") == "reference" for row in rows
        ),
        "archived_pdf_count": sum(
            row.get("recommended_storage") == "archive" for row in rows
        ),
        "direct_pdf_rag_count": sum(
            row.get("direct_pdf_rag") != "NO" for row in rows
        ),
    }


def validate_conflicts(errors: list[str]) -> set[str]:
    with (CORPUS / "conflicts.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row["conflict_id"] for row in rows]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Duplicate conflict IDs: {duplicates}")
    return set(ids)


def validate_cards(
    cards: list[dict],
    sources: dict[str, dict],
    conflict_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> dict:
    ids = [card.get("protocol_id", "") for card in cards]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Duplicate protocol IDs: {duplicates}")

    by_id = {}
    runtime_ready = 0
    critical_count = 0
    source_gap_cards = 0
    for card in cards:
        protocol_id = card.get("protocol_id", "<missing>")
        by_id[protocol_id] = card
        missing = REQUIRED_CARD_FIELDS - set(card)
        if missing:
            errors.append(f"{protocol_id}: missing fields {sorted(missing)}")
            continue

        classification = card["classification"]
        if classification.get("hazard") not in HAZARDS:
            errors.append(f"{protocol_id}: invalid hazard")
        settings = set(classification.get("settings", []))
        if not settings or not settings <= SETTINGS:
            errors.append(f"{protocol_id}: invalid settings")
        if classification.get("phase") not in PHASES:
            errors.append(f"{protocol_id}: invalid phase")
        if classification.get("actor_role") != "learner":
            errors.append(f"{protocol_id}: protocol card actor must be learner")

        languages = card["language_pack"]
        if set(languages) != LOCALES:
            errors.append(f"{protocol_id}: must contain exactly {sorted(LOCALES)}")
        for locale in LOCALES:
            localized = languages.get(locale, {})
            for field in ("short_command", "instruction", "tts_text"):
                if not str(localized.get(field, "")).strip():
                    errors.append(f"{protocol_id}:{locale}: empty {field}")

        safety = card["deterministic_safety"]
        if safety.get("criticality") == "P0_CRITICAL":
            critical_count += 1
            if safety.get("generation_mode") != "EXACT_APPROVED_TEXT":
                errors.append(f"{protocol_id}: P0 must use exact approved text")
            if not safety.get("hard_guard"):
                errors.append(f"{protocol_id}: P0 must be a hard guard")

        for action in card["approved_semantics"].get("ordered_actions", []):
            for label, pattern in UNSAFE_ORDERED_ACTION_PATTERNS.items():
                if pattern.search(action):
                    errors.append(
                        f"{protocol_id}: ordered action matched unsafe pattern "
                        f"'{label}': {action}"
                    )

        claims = card["provenance"].get("source_claims", [])
        if not claims:
            errors.append(f"{protocol_id}: no source claim")
        for claim in claims:
            source_id = claim.get("source_id")
            if source_id not in sources:
                errors.append(f"{protocol_id}: unknown source {source_id}")
                continue
            if not str(claim.get("locator", "")).strip():
                errors.append(f"{protocol_id}: source {source_id} lacks locator")
            source = sources[source_id]
            pages = claim.get("pages", [])
            if source["source_type"] == "pdf":
                max_page = int(source["pages"])
                if not pages:
                    errors.append(f"{protocol_id}: PDF source {source_id} lacks pages")
                for page in pages:
                    if not isinstance(page, int) or page < 1 or page > max_page:
                        errors.append(
                            f"{protocol_id}: invalid page {page} for {source_id}"
                        )
                quarantined = QUARANTINED_SOURCE_PAGES.get(source_id, set())
                used_quarantined = sorted(set(pages) & quarantined)
                if (
                    used_quarantined
                    and claim.get("disposition") != "CONFLICT_REVIEW"
                ):
                    errors.append(
                        f"{protocol_id}: quarantined source pages "
                        f"{used_quarantined} for {source_id} may only be "
                        "recorded as CONFLICT_REVIEW evidence"
                    )
            elif pages:
                warnings.append(
                    f"{protocol_id}: web source {source_id} should normally have no PDF pages"
                )

        for conflict_id in card["provenance"].get("conflict_ids", []):
            if conflict_id not in conflict_ids:
                errors.append(f"{protocol_id}: unknown conflict {conflict_id}")

        review = card["review"]
        state = review.get("lifecycle_state")
        if state == "NEEDS_CURRENT_SOURCE":
            source_gap_cards += 1
        required = set(review.get("required_approvals", []))
        completed = set(review.get("completed_approvals", []))
        if state == "RUNTIME_APPROVED":
            runtime_ready += 1
            if required - completed:
                errors.append(
                    f"{protocol_id}: runtime approved with missing approvals "
                    f"{sorted(required - completed)}"
                )
        elif state not in BLOCKED_RUNTIME_STATES:
            errors.append(f"{protocol_id}: unknown or unsafe lifecycle state {state}")

    coverage = {}
    for hazard, setting, phase in product(HAZARDS, SETTINGS, PHASES):
        key = f"{hazard}:{setting}:{phase}"
        matching = [
            card["protocol_id"]
            for card in cards
            if card.get("classification", {}).get("hazard") == hazard
            and setting in card.get("classification", {}).get("settings", [])
            and card.get("classification", {}).get("phase") == phase
        ]
        coverage[key] = matching
        if not matching:
            errors.append(f"Missing context bundle: {key}")

    return {
        "by_id": by_id,
        "coverage": coverage,
        "critical_cards": critical_count,
        "runtime_approved_cards": runtime_ready,
        "source_gap_cards": source_gap_cards,
    }


def validate_tests(
    tests: list[dict], card_ids: set[str], errors: list[str]
) -> dict:
    ids = [test.get("test_id", "") for test in tests]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Duplicate validation test IDs: {duplicates}")
    for test in tests:
        test_id = test.get("test_id", "<missing>")
        expected = test.get("expected_protocol_id")
        if expected is not None and expected not in card_ids:
            errors.append(f"{test_id}: unknown expected protocol {expected}")
        if not test.get("must_assert"):
            errors.append(f"{test_id}: no positive assertion")
        if not test.get("must_reject"):
            errors.append(f"{test_id}: no rejection assertion")
    return {
        "count": len(tests),
        "categories": sorted({test.get("category", "") for test in tests}),
    }


def validate_retrieval_units(
    cards: list[dict], errors: list[str]
) -> dict:
    review_units = load_jsonl(
        CORPUS / "retrieval" / "review_candidate_units.jsonl", errors
    )
    runtime_units = load_jsonl(
        CORPUS / "retrieval" / "runtime_units.jsonl", errors
    )
    expected_count = len(cards) * len(LOCALES)
    if len(review_units) != expected_count:
        errors.append(
            f"Review retrieval-unit count is {len(review_units)}; "
            f"expected {expected_count}"
        )
    ids = [unit.get("retrieval_id", "") for unit in review_units]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate review retrieval IDs")

    boilerplate = re.compile(
        r"\b(acknowledg|trunkline|isbn|published by|copyright owner)\b|"
        r"https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        re.IGNORECASE,
    )
    for unit in review_units:
        if unit.get("locale") not in LOCALES:
            errors.append(
                f"{unit.get('retrieval_id', '<missing>')}: invalid locale"
            )
        if boilerplate.search(unit.get("embedding_text", "")):
            errors.append(
                f"{unit.get('retrieval_id', '<missing>')}: embedding contains "
                "source/contact boilerplate"
            )
    for unit in runtime_units:
        if unit.get("lifecycle_state") != "RUNTIME_APPROVED":
            errors.append(
                f"{unit.get('retrieval_id', '<missing>')}: non-approved runtime unit"
            )
    expected_runtime = sum(
        card["review"]["lifecycle_state"] == "RUNTIME_APPROVED"
        for card in cards
    ) * len(LOCALES)
    if len(runtime_units) != expected_runtime:
        errors.append(
            f"Runtime retrieval-unit count is {len(runtime_units)}; "
            f"expected {expected_runtime}"
        )
    return {
        "review_candidate_units": len(review_units),
        "runtime_units": len(runtime_units),
    }


def main() -> None:
    errors: list[str] = []
    warnings: list[str] = []

    sources = validate_sources(errors, warnings)
    derivation_metrics = validate_pdf_derivation_matrix(sources, errors)
    conflicts = validate_conflicts(errors)
    cards = load_jsonl(CORPUS / "protocol_cards.jsonl", errors)
    card_metrics = validate_cards(cards, sources, conflicts, errors, warnings)
    tests = load_jsonl(CORPUS / "validation_cases.jsonl", errors)
    test_metrics = validate_tests(tests, set(card_metrics["by_id"]), errors)
    retrieval_metrics = validate_retrieval_units(cards, errors)

    report = {
        "status": "PASS" if not errors else "FAIL",
        "corpus_version": "1.0",
        "source_count": len(sources),
        "pdf_source_count": sum(
            source["source_type"] == "pdf" for source in sources.values()
        ),
        "web_source_count": sum(
            source["source_type"] == "web" for source in sources.values()
        ),
        "pdf_derivation_audit": derivation_metrics,
        "protocol_card_count": len(cards),
        "context_bundle_count": sum(
            bool(items) for items in card_metrics["coverage"].values()
        ),
        "required_context_bundle_count": 27,
        "critical_card_count": card_metrics["critical_cards"],
        "runtime_approved_card_count": card_metrics["runtime_approved_cards"],
        "source_gap_card_count": card_metrics["source_gap_cards"],
        "validation_case_count": test_metrics["count"],
        "review_candidate_retrieval_unit_count": retrieval_metrics[
            "review_candidate_units"
        ],
        "runtime_retrieval_unit_count": retrieval_metrics["runtime_units"],
        "validation_categories": test_metrics["categories"],
        "errors": errors,
        "warnings": warnings,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
