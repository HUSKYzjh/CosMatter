#!/usr/bin/env python3
"""Bridge a private MinerU library to CosMatter's human-review corpus flow.

The utility intentionally has two explicit phases:

``template``
    Builds a metadata-only review sheet from the private parse catalogue.
``freeze``
    Validates a fully human-reviewed sheet and writes (outside a run) both a
    corpus-selection review accepted by ``record-corpus-manifest-from-selection-review``
    and a path-bearing local-search index.  The latter is process-local input
    only; it must never be copied into a run, ui.json, or a run package.

Neither command reads Markdown contents.  A private library catalogue remains
unreviewed material until a human marks every row and later creates source maps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CATALOG_STATUS = "private_parsed_library_catalog_not_corpus_not_evidence"
TEMPLATE_STATUS = "blank_human_private_library_cohort_review_template_not_corpus"
REVIEW_STATUS = "human_reviewed_private_library_cohort_selection"
ACCESS = "institutional_access_internal_review_only"


class BridgeError(ValueError):
    """Raised for a malformed or unsafe private-library review operation."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BridgeError(f"cannot read JSON: {path.name}") from error


def _write_new_json(path: Path, payload: object) -> None:
    if path.exists():
        raise BridgeError(f"refusing to overwrite existing file: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fingerprint(rows: list[dict[str, Any]]) -> str:
    # Match build_private_library_catalog_v3.py exactly: the fingerprint binds
    # both metadata and the private relative-path/parse-state boundary, while
    # the outputs below deliberately omit that path from review sheets.
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _catalog(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or payload.get("trust_status") != CATALOG_STATUS:
        raise BridgeError("input must be a private parsed-library catalogue, not a corpus or evidence artifact")
    rows = payload.get("documents")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 250:
        raise BridgeError("private catalogue must contain 1 to 250 documents")
    ids: set[str] = set()
    checked: list[dict[str, Any]] = []
    required = {
        "document_id", "provisional_title", "source_group", "markdown_sha256",
        "private_markdown_relative_path", "parse_state", "classification", "evidence_status",
    }
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise BridgeError("private catalogue document fields are invalid")
        if row["parse_state"] != "done" or row["classification"] != "unreviewed" or row["evidence_status"] != "not_evidence_requires_human_source_map_review":
            raise BridgeError("private catalogue records must retain their unreviewed non-evidence state")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in required):
            raise BridgeError("private catalogue document values are invalid")
        if row["document_id"] in ids:
            raise BridgeError("private catalogue document IDs must be unique")
        ids.add(row["document_id"])
        checked.append(row)
    if payload.get("catalog_fingerprint") != _fingerprint(checked):
        raise BridgeError("private catalogue fingerprint does not match its document metadata")
    return payload, checked


def make_template(args: argparse.Namespace) -> int:
    catalog, documents = _catalog(args.catalog)
    if not all(isinstance(value, str) and value.strip() for value in (args.mission_id, args.material, args.query, args.corpus_id)):
        raise BridgeError("mission ID, material, query, and corpus ID must be nonempty")
    rows = [
        {
            "document_id": item["document_id"],
            "provisional_title": item["provisional_title"],
            "source_group": item["source_group"],
            "markdown_sha256": item["markdown_sha256"],
            "include_for_corpus": "unreviewed",
            "reviewed_title": "",
            "doi": None,
            "material_scope_match": "unreviewed",
            "access_authorized": "unreviewed",
            "review_reason": "",
        }
        for item in documents
    ]
    payload = {
        "schema_version": "1.0",
        "catalog_fingerprint": catalog["catalog_fingerprint"],
        "mission_id": args.mission_id.strip(),
        "corpus_id": args.corpus_id.strip(),
        "material": args.material.strip(),
        "query": args.query.strip(),
        "trust_status": TEMPLATE_STATUS,
        "instructions": [
            "Review every row before freezing a corpus; do not rely on a file name alone.",
            "For each row, set include_for_corpus to true or false, material_scope_match and access_authorized to true or false, and provide a nonempty review_reason.",
            "Selected rows must have a reviewed_title. DOI may be null only after a manual DOI check.",
            "This private review remains metadata-only. Parsed Markdown is not evidence and still requires a human-reviewed Source Map.",
        ],
        "candidates": rows,
    }
    _write_new_json(args.output, payload)
    print(json.dumps({"status": "template_created", "candidate_count": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


def _valid_doi(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BridgeError("DOI must be a string or null")
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    if not normalized.startswith("10.") or "/" not in normalized or len(normalized) > 300:
        raise BridgeError("DOI is not syntactically usable; use null only after a manual DOI check")
    return normalized


def _reviewed_rows(review: object, catalog: dict[str, Any], documents: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if not isinstance(review, dict):
        raise BridgeError("review must be a JSON object")
    expected = {"schema_version", "catalog_fingerprint", "mission_id", "corpus_id", "material", "query", "trust_status", "instructions", "candidates"}
    if set(review) != expected or review.get("schema_version") != "1.0" or review.get("trust_status") != REVIEW_STATUS:
        raise BridgeError("review must be a completed private-library cohort review")
    if review.get("catalog_fingerprint") != catalog["catalog_fingerprint"]:
        raise BridgeError("review does not match this private catalogue")
    if any(review.get(key) != getattr(args, key) for key in ("mission_id", "corpus_id", "material", "query")):
        raise BridgeError("review mission fields must match the requested freeze operation")
    candidates = review.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(documents):
        raise BridgeError("review must decide every catalogue row")
    originals = {item["document_id"]: item for item in documents}
    reviewed: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_fields = {
        "document_id", "provisional_title", "source_group", "markdown_sha256", "include_for_corpus",
        "reviewed_title", "doi", "material_scope_match", "access_authorized", "review_reason",
    }
    for item in candidates:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise BridgeError("review candidate fields are invalid")
        document_id = item.get("document_id")
        original = originals.get(document_id) if isinstance(document_id, str) else None
        if original is None or document_id in seen:
            raise BridgeError("review candidate ID is invalid or duplicated")
        if any(item.get(key) != original[key] for key in ("provisional_title", "source_group", "markdown_sha256")):
            raise BridgeError("review cannot alter catalogue identity fields")
        if not isinstance(item.get("include_for_corpus"), bool) or not isinstance(item.get("material_scope_match"), bool) or not isinstance(item.get("access_authorized"), bool):
            raise BridgeError("every review decision must be explicit true or false")
        reason = item.get("review_reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise BridgeError("every review decision requires a nonempty concise reason")
        title = item.get("reviewed_title")
        if item["include_for_corpus"]:
            if item["material_scope_match"] is not True or item["access_authorized"] is not True:
                raise BridgeError("selected rows require both material/scope and access authorization")
            if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
                raise BridgeError("selected rows require a reviewed title")
        elif not isinstance(title, str) or len(title.strip()) > 500:
            raise BridgeError("reviewed_title must be a string")
        reviewed.append({**item, "doi": _valid_doi(item.get("doi")), "reviewed_title": title.strip() if isinstance(title, str) else ""})
        seen.add(document_id)
    return reviewed


def freeze(args: argparse.Namespace) -> int:
    catalog, documents = _catalog(args.catalog)
    review = _load_json(args.review)
    rows = _reviewed_rows(review, catalog, documents, args)
    selected = [row for row in rows if row["include_for_corpus"]]
    if not 1 <= len(selected) <= 250:
        raise BridgeError("review must select between 1 and 250 documents")
    dois: set[str] = set()
    for row in selected:
        if row["doi"] is not None:
            if row["doi"] in dois:
                raise BridgeError("selected rows have duplicate normalized DOIs")
            dois.add(row["doi"])
    root = args.markdown_root.resolve()
    if not root.is_dir():
        raise BridgeError("private Markdown root does not exist")
    document_lookup = {row["document_id"]: row for row in documents}
    local_documents: list[dict[str, str]] = []
    selection_cards: list[dict[str, Any]] = []
    for row in selected:
        source = document_lookup[row["document_id"]]
        markdown = (root / source["private_markdown_relative_path"]).resolve()
        try:
            markdown.relative_to(root)
        except ValueError as error:
            raise BridgeError("private Markdown path escapes the configured root") from error
        if not markdown.is_file() or markdown.suffix.casefold() not in {".md", ".markdown"}:
            raise BridgeError("selected private Markdown file is missing or not Markdown")
        local_documents.append({
            "document_id": row["document_id"],
            "title": row["reviewed_title"],
            "path": str(markdown),
            "parser_provenance": "mineru_reviewed_local_output",
        })
        selection_cards.append({
            "document_id": row["document_id"], "title": row["reviewed_title"], "doi": row["doi"],
            "include_for_corpus": True, "review_reason": row["review_reason"],
        })
    corpus_selection = {
        "schema_version": "1.0", "mission_id": args.mission_id, "corpus_id": args.corpus_id,
        "material": args.material, "query": args.query,
        "candidate_fingerprint": _selection_fingerprint(selection_cards),
        "trust_status": "human_reviewed_corpus_selection_for_manifest", "candidates": selection_cards,
    }
    # The current core workflow verifies the fingerprint over all reviewed cards.
    # To preserve its schema, include rejected rows as explicit decisions too.
    core_cards = [
        {"document_id": row["document_id"], "title": row["reviewed_title"] or row["provisional_title"], "doi": row["doi"],
         "include_for_corpus": row["include_for_corpus"], "review_reason": row["review_reason"]}
        for row in rows
    ]
    corpus_selection["candidates"] = core_cards
    corpus_selection["candidate_fingerprint"] = _selection_fingerprint(core_cards)
    output = args.output.resolve()
    _write_new_json(output / "corpus_selection_review.json", corpus_selection)
    _write_new_json(output / "local_source_index.json", {"documents": local_documents})
    _write_new_json(output / "freeze_receipt.json", {
        "schema_version": "1.0", "trust_status": "private_human_review_freeze_receipt_not_evaluation_result",
        "catalog_fingerprint": catalog["catalog_fingerprint"], "mission_id": args.mission_id,
        "corpus_id": args.corpus_id, "selected_document_count": len(selected),
        "doi_count": len(dois), "documents_with_no_doi": sum(row["doi"] is None for row in selected),
        "next_step": "record corpus_selection_review.json through the CosMatter CLI; retain local_source_index.json outside the run",
    })
    print(json.dumps({"status": "frozen", "selected_document_count": len(selected), "output": str(output)}, ensure_ascii=False))
    return 0


def _selection_fingerprint(cards: list[dict[str, Any]]) -> str:
    stable = [{key: item[key] for key in ("document_id", "title", "doi")} for item in cards]
    encoded = json.dumps(stable, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("template", "freeze"):
        command = commands.add_parser(name)
        command.add_argument("--catalog", type=Path, required=True)
        command.add_argument("--mission-id", required=True)
        command.add_argument("--corpus-id", required=True)
        command.add_argument("--material", required=True)
        command.add_argument("--query", required=True)
    template = commands.choices["template"]
    template.add_argument("--output", type=Path, required=True)
    freeze_command = commands.choices["freeze"]
    freeze_command.add_argument("--review", type=Path, required=True)
    freeze_command.add_argument("--markdown-root", type=Path, required=True)
    freeze_command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return make_template(args) if args.command == "template" else freeze(args)
    except BridgeError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
