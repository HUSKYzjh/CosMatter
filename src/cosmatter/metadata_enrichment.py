"""Conflict-safe DOI enrichment for an already screened candidate set.

Provider search results remain metadata, not evidence.  Resolution is accepted
only for an exact normalized-title match with a compatible publication year.
Distinct matching DOIs are retained as a conflict and never merged silently.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from .candidate_screening import candidate_fingerprint
from .models import PaperCandidate, normalized_doi_or_none


SCHEMA_VERSION = "1.0"
TRUST_STATUS = "provider_metadata_resolution_not_scientific_evidence"
_PROVIDERS = {"Crossref", "OpenAlex"}
_STATUSES = {"already_present", "resolved", "not_found", "conflict", "provider_failed"}
_MAX_BATCH_DOCUMENTS = 12
_MAX_AGGREGATE_DOCUMENTS = 5_000
_ROOT_FIELDS = {
    "schema_version", "mission_id", "trust_status", "candidate_fingerprint",
    "requested_document_count", "records", "summary",
}
_RECORD_FIELDS = {"document_id", "status", "doi", "sources", "exact_match_count"}
_SUMMARY_FIELDS = {
    "already_present_count", "resolved_count", "not_found_count", "conflict_count",
    "provider_failed_count", "provider_call_failure_count",
}


class MetadataEnrichmentError(ValueError):
    """Raised when metadata resolution cannot be represented safely."""


def build_metadata_enrichment(
    mission_id: str,
    candidate_payload: object,
    document_ids: tuple[str, ...],
    provider_results: Mapping[str, Mapping[str, tuple[PaperCandidate, ...] | None]],
) -> dict[str, Any]:
    """Resolve screened candidate DOIs from bounded provider result sets.

    ``None`` for one provider means that provider call failed.  An empty tuple
    means the call succeeded but returned no usable records.
    """
    if not isinstance(mission_id, str) or not mission_id.strip() or len(mission_id.strip()) > 160:
        raise MetadataEnrichmentError("mission_id is invalid")
    candidates = _candidate_index(candidate_payload)
    if (
        not isinstance(document_ids, tuple)
        or not 1 <= len(document_ids) <= _MAX_BATCH_DOCUMENTS
        or len(set(document_ids)) != len(document_ids)
        or any(document_id not in candidates for document_id in document_ids)
    ):
        raise MetadataEnrichmentError("metadata enrichment requires 1 to 12 unique current candidate IDs")
    if set(provider_results) != set(document_ids):
        raise MetadataEnrichmentError("metadata provider results do not match the requested candidate set")

    records: list[dict[str, Any]] = []
    provider_call_failure_count = 0
    for document_id in document_ids:
        candidate = candidates[document_id]
        existing_doi = normalized_doi_or_none(candidate.get("doi"))
        sources: set[str] = set()
        exact_matches: list[PaperCandidate] = []
        results = provider_results[document_id]
        if not isinstance(results, Mapping) or not results or not set(results).issubset(_PROVIDERS):
            raise MetadataEnrichmentError("metadata provider result map is invalid")
        successful_provider_count = 0
        for provider, provider_candidates in results.items():
            if provider_candidates is None:
                provider_call_failure_count += 1
                continue
            if not isinstance(provider_candidates, tuple) or any(not isinstance(item, PaperCandidate) for item in provider_candidates):
                raise MetadataEnrichmentError("metadata provider candidates are invalid")
            successful_provider_count += 1
            for provider_candidate in provider_candidates:
                if _exact_identity_match(candidate, provider_candidate) and provider_candidate.doi is not None:
                    exact_matches.append(provider_candidate)
                    sources.add(provider)

        matching_dois = sorted({item.doi for item in exact_matches if item.doi is not None})
        if existing_doi is not None:
            status, resolved_doi = "already_present", existing_doi
        elif len(matching_dois) == 1:
            status, resolved_doi = "resolved", matching_dois[0]
        elif len(matching_dois) > 1:
            status, resolved_doi = "conflict", None
        elif successful_provider_count == 0:
            status, resolved_doi = "provider_failed", None
        else:
            status, resolved_doi = "not_found", None
        records.append(
            {
                "document_id": document_id,
                "status": status,
                "doi": resolved_doi,
                "sources": sorted(sources),
                "exact_match_count": len(exact_matches),
            }
        )

    summary = {f"{status}_count": sum(record["status"] == status for record in records) for status in _STATUSES}
    summary["provider_call_failure_count"] = provider_call_failure_count
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id.strip(),
        "trust_status": TRUST_STATUS,
        "candidate_fingerprint": candidate_fingerprint(candidate_payload),
        "requested_document_count": len(document_ids),
        "records": records,
        "summary": summary,
    }
    _validate(artifact)
    return artifact


def merge_metadata_enrichment(
    existing: object | None,
    batch: object,
    mission_id: str,
    candidate_payload: object,
) -> dict[str, Any]:
    """Merge one bounded provider batch into a current cumulative artifact.

    Provider calls remain capped by :func:`build_metadata_enrichment`; only the
    local aggregate may grow beyond one batch. Existing records are immutable,
    so a retry cannot silently replace a prior DOI resolution or conflict.
    """
    _validate(batch)
    fingerprint = candidate_fingerprint(candidate_payload)
    if batch["mission_id"] != mission_id or batch["candidate_fingerprint"] != fingerprint:
        raise MetadataEnrichmentError("metadata enrichment batch is stale or belongs to another mission")
    if batch["requested_document_count"] > _MAX_BATCH_DOCUMENTS:
        raise MetadataEnrichmentError("metadata enrichment batch exceeds the provider-call boundary")
    if existing is None:
        return dict(batch)
    _validate(existing)
    if existing["mission_id"] != mission_id or existing["candidate_fingerprint"] != fingerprint:
        raise MetadataEnrichmentError("existing metadata enrichment is stale or belongs to another mission")
    existing_ids = {record["document_id"] for record in existing["records"]}
    batch_ids = {record["document_id"] for record in batch["records"]}
    candidate_ids = set(_candidate_index(candidate_payload))
    if not existing_ids.union(batch_ids).issubset(candidate_ids):
        raise MetadataEnrichmentError("metadata enrichment contains a candidate outside the current set")
    if existing_ids.intersection(batch_ids):
        raise MetadataEnrichmentError("metadata enrichment batch would overwrite an existing candidate record")
    records = [*existing["records"], *batch["records"]]
    if len(records) > _MAX_AGGREGATE_DOCUMENTS:
        raise MetadataEnrichmentError("metadata enrichment aggregate exceeds the bounded candidate limit")
    summary = {f"{status}_count": sum(record["status"] == status for record in records) for status in _STATUSES}
    summary["provider_call_failure_count"] = (
        existing["summary"]["provider_call_failure_count"]
        + batch["summary"]["provider_call_failure_count"]
    )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": TRUST_STATUS,
        "candidate_fingerprint": fingerprint,
        "requested_document_count": len(records),
        "records": records,
        "summary": summary,
    }
    _validate(artifact)
    return artifact


def write_metadata_enrichment(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate(artifact)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "candidate_metadata_enrichment.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_metadata_enrichment(path: Path, mission_id: str, candidate_payload: object) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MetadataEnrichmentError("candidate metadata enrichment is invalid JSON") from error
    _validate(artifact)
    if artifact["mission_id"] != mission_id or artifact["candidate_fingerprint"] != candidate_fingerprint(candidate_payload):
        raise MetadataEnrichmentError("candidate metadata enrichment is stale or belongs to another mission")
    return artifact


def resolved_dois(artifact: object | None) -> dict[str, str]:
    if artifact is None:
        return {}
    _validate(artifact)
    return {
        record["document_id"]: record["doi"]
        for record in artifact["records"]
        if record["status"] in {"already_present", "resolved"} and isinstance(record["doi"], str)
    }


def resolved_dois_for_candidates(artifact: object | None, mission_id: str, candidate_payload: object) -> dict[str, str]:
    """Return DOI mappings only when the artifact is current for this mission."""
    if artifact is None:
        return {}
    _validate(artifact)
    if artifact["mission_id"] != mission_id or artifact["candidate_fingerprint"] != candidate_fingerprint(candidate_payload):
        raise MetadataEnrichmentError("candidate metadata enrichment is stale or belongs to another mission")
    candidate_ids = set(_candidate_index(candidate_payload))
    if any(record["document_id"] not in candidate_ids for record in artifact["records"]):
        raise MetadataEnrichmentError("candidate metadata enrichment contains an unknown candidate")
    return resolved_dois(artifact)


def _candidate_index(payload: object) -> dict[str, dict[str, Any]]:
    raw = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(raw, list) or not raw:
        raise MetadataEnrichmentError("candidate payload must contain candidates")
    result: dict[str, dict[str, Any]] = {}
    for candidate in raw:
        document_id = candidate.get("document_id") if isinstance(candidate, dict) else None
        title = candidate.get("title") if isinstance(candidate, dict) else None
        if (
            not isinstance(document_id, str)
            or not document_id.strip()
            or document_id in result
            or not isinstance(title, str)
            or not title.strip()
        ):
            raise MetadataEnrichmentError("candidate identity metadata is invalid")
        result[document_id] = candidate
    return result


def _exact_identity_match(candidate: dict[str, Any], provider_candidate: PaperCandidate) -> bool:
    if _normalized_title(candidate["title"]) != _normalized_title(provider_candidate.title):
        return False
    candidate_year = candidate.get("publication_year")
    provider_year = provider_candidate.publication_year
    return candidate_year is None or provider_year is None or candidate_year == provider_year


def _normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip().rstrip(". ")


def _validate(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _ROOT_FIELDS:
        raise MetadataEnrichmentError("metadata enrichment fields are invalid")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != TRUST_STATUS:
        raise MetadataEnrichmentError("metadata enrichment trust boundary is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip():
        raise MetadataEnrichmentError("metadata enrichment mission is invalid")
    fingerprint = payload.get("candidate_fingerprint")
    records = payload.get("records")
    summary = payload.get("summary")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or not isinstance(records, list)
        or not 1 <= len(records) <= _MAX_AGGREGATE_DOCUMENTS
        or payload.get("requested_document_count") != len(records)
        or not isinstance(summary, dict)
        or set(summary) != _SUMMARY_FIELDS
    ):
        raise MetadataEnrichmentError("metadata enrichment identity or counts are invalid")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
            raise MetadataEnrichmentError("metadata enrichment record fields are invalid")
        document_id, status, doi, sources, count = (
            record.get("document_id"), record.get("status"), record.get("doi"), record.get("sources"), record.get("exact_match_count")
        )
        if (
            not isinstance(document_id, str)
            or not document_id.strip()
            or document_id in seen
            or status not in _STATUSES
            or not isinstance(sources, list)
            or sources != sorted(set(sources))
            or any(source not in _PROVIDERS for source in sources)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise MetadataEnrichmentError("metadata enrichment record values are invalid")
        normalized = normalized_doi_or_none(doi)
        if (status in {"already_present", "resolved"}) != (normalized is not None) or (normalized is not None and normalized != doi):
            raise MetadataEnrichmentError("metadata enrichment DOI status is inconsistent")
        seen.add(document_id)
    expected = {f"{status}_count": sum(record["status"] == status for record in records) for status in _STATUSES}
    for key, value in expected.items():
        if summary.get(key) != value:
            raise MetadataEnrichmentError("metadata enrichment summary is inconsistent")
    failures = summary.get("provider_call_failure_count")
    if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
        raise MetadataEnrichmentError("metadata enrichment provider failure count is invalid")
