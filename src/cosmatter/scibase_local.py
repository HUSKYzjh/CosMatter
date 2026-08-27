"""Build a private, DOI-bound BM25 source index from a local Sci-Base Parquet subset.

This adapter deliberately does not download Sci-Base or call an external service.
It only reads one explicit local Parquet subset supplied by the operator, matches
its Open Access records to an already human-reviewed corpus manifest by exact
normalized DOI, and writes private Markdown plus an index outside a mission run.
The run artifacts still receive only retrieval metadata.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import normalized_doi_or_none


class SciBaseLocalError(ValueError):
    """Raised when a local Sci-Base subset is unsafe, incomplete, or malformed."""


_INDEX_NAME = "scibase_local_source_index.json"
_RECEIPT_NAME = "scibase_local_index_receipt.json"
_MARKDOWN_DIRECTORY = "scibase_markdown"
_PROVENANCE = "scibase_parquet_oa_subset"
_MAX_DOCUMENT_BYTES = 5_000_000
_MAX_TOTAL_BYTES = 100_000_000
_DEFAULT_MAX_ROWS = 500_000
_MAX_ROWS = 5_000_000
_TEXT_FIELDS = ("text", "text_content", "content", "markdown")


@dataclass(frozen=True)
class SciBaseIndexBuildResult:
    index_path: Path
    receipt_path: Path
    matched_document_count: int
    manifest_document_count: int
    manifest_documents_without_doi: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_path": str(self.index_path),
            "receipt_path": str(self.receipt_path),
            "matched_document_count": self.matched_document_count,
            "manifest_document_count": self.manifest_document_count,
            "manifest_documents_without_doi": self.manifest_documents_without_doi,
        }


def rows_from_scibase_parquet(path: Path, *, max_rows: int = _DEFAULT_MAX_ROWS) -> Iterator[dict[str, Any]]:
    """Yield a bounded sample from a locally available Sci-Base Parquet file.

    PyArrow is optional because the normal CosMatter workflow has no binary
    dependency. Install the project's scibase optional extra before using this
    adapter. The source file is never copied into a mission run.
    """
    if not isinstance(max_rows, int) or not 1 <= max_rows <= _MAX_ROWS:
        raise SciBaseLocalError(f"max_rows must be between 1 and {_MAX_ROWS}")
    if path.suffix.casefold() != ".parquet":
        raise SciBaseLocalError("Sci-Base input must be one explicit .parquet file")
    try:
        import pyarrow.parquet as parquet  # type: ignore[import-not-found]
    except ImportError as error:
        raise SciBaseLocalError(
            "Sci-Base Parquet import requires optional dependency pyarrow; install the scibase extra"
        ) from error
    try:
        reader = parquet.ParquetFile(path)
    except (OSError, ValueError) as error:
        raise SciBaseLocalError("Sci-Base Parquet input cannot be opened") from error
    available = set(reader.schema.names)
    required = {"sha256", "title", "doi", "is_oa", "content_list"}
    missing = required - available
    if missing:
        raise SciBaseLocalError(f"Sci-Base Parquet input lacks required columns: {', '.join(sorted(missing))}")
    columns = [name for name in ("sha256", "title", "doi", "is_oa", "abstract", "content_list") if name in available]
    emitted = 0
    try:
        batches = reader.iter_batches(batch_size=1024, columns=columns)
        for batch in batches:
            for row in batch.to_pylist():
                yield row
                emitted += 1
                if emitted >= max_rows:
                    return
    except (OSError, ValueError) as error:
        raise SciBaseLocalError("Sci-Base Parquet rows cannot be read") from error


def build_scibase_local_index(
    *,
    manifest: object,
    rows: Iterable[Mapping[str, Any]],
    output_dir: Path,
    dataset_id: str = "opendatalab/Sci-Base",
    dataset_revision: str | None = None,
    require_all_doi_matched: bool = False,
) -> SciBaseIndexBuildResult:
    """Write a private Markdown/index pair from exact-DOI matches only.

    rows can be supplied by rows_from_scibase_parquet or by an offline test
    fixture. No title-only matching is allowed, so a row cannot be silently
    attached to the wrong reviewed corpus paper.
    """
    documents = _manifest_documents(manifest)
    if not isinstance(dataset_id, str) or not dataset_id.strip() or len(dataset_id) > 240:
        raise SciBaseLocalError("dataset_id is invalid")
    if dataset_revision is not None and (not isinstance(dataset_revision, str) or not dataset_revision.strip() or len(dataset_revision) > 240):
        raise SciBaseLocalError("dataset_revision is invalid")
    target = output_dir.resolve()
    if target.exists() and any(target.iterdir()):
        raise SciBaseLocalError("output_dir must be a new or empty private directory; existing files are not overwritten")
    by_doi: dict[str, dict[str, str | None]] = {}
    without_doi = 0
    for item in documents:
        doi = normalized_doi_or_none(item["doi"])
        if doi is None:
            without_doi += 1
            continue
        if doi in by_doi:
            raise SciBaseLocalError("authorized corpus manifest has duplicate DOI values; resolve them before Sci-Base import")
        by_doi[doi] = item
    if not by_doi:
        raise SciBaseLocalError("Sci-Base import requires at least one reviewed manifest document with a DOI")

    matched: dict[str, tuple[dict[str, str | None], str, str]] = {}
    total_bytes = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise SciBaseLocalError("Sci-Base row is not an object")
        doi = normalized_doi_or_none(row.get("doi"))
        if doi is None or doi not in by_doi:
            continue
        document = by_doi[doi]
        document_id = str(document["document_id"])
        if document_id in matched:
            raise SciBaseLocalError("Sci-Base subset contains multiple rows for one reviewed DOI")
        if row.get("is_oa") is not True:
            raise SciBaseLocalError("Sci-Base matched record is not marked Open Access")
        source_hash = row.get("sha256")
        if not isinstance(source_hash, str) or len(source_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in source_hash):
            raise SciBaseLocalError("Sci-Base matched record lacks a valid sha256 identifier")
        content = _markdown_content(row, str(document["title"]))
        encoded_size = len(content.encode("utf-8"))
        if encoded_size > _MAX_DOCUMENT_BYTES:
            raise SciBaseLocalError("Sci-Base matched document exceeds the private local-index byte limit")
        total_bytes += encoded_size
        if total_bytes > _MAX_TOTAL_BYTES:
            raise SciBaseLocalError("Sci-Base matched subset exceeds the private local-index byte limit")
        matched[document_id] = (document, source_hash.casefold(), content)

    if not matched:
        raise SciBaseLocalError("no reviewed manifest DOI was found in the supplied Sci-Base subset")
    if require_all_doi_matched and set(matched) != {str(item["document_id"]) for item in by_doi.values()}:
        raise SciBaseLocalError("the supplied Sci-Base subset does not cover every DOI-bearing reviewed manifest document")

    target.mkdir(parents=True, exist_ok=True)
    markdown_dir = target / _MARKDOWN_DIRECTORY
    markdown_dir.mkdir()
    index_documents: list[dict[str, str]] = []
    for document_id in sorted(matched):
        document, source_hash, content = matched[document_id]
        filename = hashlib.sha256(document_id.encode("utf-8")).hexdigest() + ".md"
        markdown_path = markdown_dir / filename
        markdown_path.write_text(content, encoding="utf-8")
        index_documents.append({
            "document_id": document_id,
            "title": str(document["title"]),
            "path": str(markdown_path),
            "parser_provenance": _PROVENANCE,
        })
    index_path = target / _INDEX_NAME
    index_path.write_text(json.dumps({"documents": index_documents}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt_path = target / _RECEIPT_NAME
    receipt = {
        "schema_version": "1.0",
        "dataset_id": dataset_id.strip(),
        "dataset_revision": dataset_revision.strip() if isinstance(dataset_revision, str) else None,
        "dataset_format": "parquet",
        "match_policy": "exact_normalized_doi_only",
        "source_access_requirement": "is_oa_true",
        "matched_document_count": len(index_documents),
        "manifest_document_count": len(documents),
        "manifest_documents_without_doi": without_doi,
        "unmatched_doi_bearing_manifest_document_count": len(by_doi) - len(matched),
        "local_index_provenance": _PROVENANCE,
        "license_notice": "Dataset structure is documented as CC-BY-4.0; downstream use must still check each original document's OA license.",
        "run_artifact_boundary": "private_markdown_and_paths_remain_outside_mission_run",
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SciBaseIndexBuildResult(
        index_path=index_path,
        receipt_path=receipt_path,
        matched_document_count=len(index_documents),
        manifest_document_count=len(documents),
        manifest_documents_without_doi=without_doi,
    )


def _manifest_documents(manifest: object) -> list[dict[str, str | None]]:
    if not isinstance(manifest, dict) or manifest.get("trust_status") != "human_reviewed_authorized_corpus_manifest_not_evaluation_result":
        raise SciBaseLocalError("Sci-Base import requires a human-reviewed authorized corpus manifest")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= 250:
        raise SciBaseLocalError("authorized corpus manifest documents are invalid")
    result: list[dict[str, str | None]] = []
    ids: set[str] = set()
    for item in documents:
        if not isinstance(item, dict) or item.get("access_policy") != "institutional_access_internal_review_only":
            raise SciBaseLocalError("Sci-Base import requires institutionally authorized reviewed documents")
        document_id, title = item.get("document_id"), item.get("title")
        if not isinstance(document_id, str) or not document_id or document_id in ids or not isinstance(title, str) or not title:
            raise SciBaseLocalError("authorized corpus manifest identity is invalid")
        ids.add(document_id)
        result.append({"document_id": document_id, "title": title, "doi": item.get("doi")})
    return result


def _markdown_content(row: Mapping[str, Any], title: str) -> str:
    fragments: list[str] = []
    abstract = row.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        fragments.append(abstract.strip())
    content_list = row.get("content_list")
    if not isinstance(content_list, list):
        raise SciBaseLocalError("Sci-Base matched record content_list is invalid")
    for item in content_list:
        if isinstance(item, str) and item.strip():
            fragments.append(item.strip())
        elif isinstance(item, Mapping):
            for field in _TEXT_FIELDS:
                value = item.get(field)
                if isinstance(value, str) and value.strip():
                    fragments.append(value.strip())
    if not fragments:
        raise SciBaseLocalError("Sci-Base matched record has no supported text fragments")
    return "# " + title.strip() + "\n\n" + "\n\n".join(fragments) + "\n"
