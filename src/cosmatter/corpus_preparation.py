"""Human-reviewed, authorization-bounded corpus manifests and annotation templates.

This module intentionally consumes an explicit bibliographic manifest. It never
walks a local PDF directory, reads attachments, or records local filesystem
paths. A reviewer decides which institutionally authorized papers belong to a
frozen evaluation cohort before any full-text work begins.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from .models import PaperCandidate, normalized_doi_or_none


CORPUS_MANIFEST_SCHEMA_VERSION = "1.0"
CORPUS_SELECTION_TEMPLATE_SCHEMA_VERSION = "1.0"
GOLD_STANDARD_TEMPLATE_SCHEMA_VERSION = "1.0"
_ACCESS_POLICY = "institutional_access_internal_review_only"
_MANIFEST_INPUT_FIELDS = {"corpus_id", "material", "documents"}
_DOCUMENT_FIELDS = {"document_id", "title", "doi", "access_policy"}
_MANIFEST_FIELDS = {
    "schema_version", "mission_id", "corpus_id", "material", "trust_status",
    "access_boundary", "documents",
}
_SELECTION_TEMPLATE_FIELDS = {
    "schema_version", "mission_id", "corpus_id", "material", "query",
    "candidate_fingerprint", "trust_status", "candidates",
}
_SELECTION_CANDIDATE_FIELDS = {
    "document_id", "title", "doi", "include_for_corpus", "review_reason",
}


class CorpusPreparationError(ValueError):
    """Raised for unsafe, incomplete, or non-reviewable corpus metadata."""


def corpus_manifest_from_review(*, mission_id: str, material: str, selection: object) -> dict[str, Any]:
    """Create a path-free manifest from a reviewer-selected bibliography."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(material, str) or not material.strip():
        raise CorpusPreparationError("mission identity and material must be nonempty")
    if not isinstance(selection, dict) or set(selection) != _MANIFEST_INPUT_FIELDS:
        raise CorpusPreparationError("corpus selection must contain only corpus_id, material, and documents")
    if selection.get("material") != material:
        raise CorpusPreparationError("corpus material must match the mission material")
    corpus_id = selection.get("corpus_id")
    if not isinstance(corpus_id, str) or not corpus_id.strip() or len(corpus_id) > 120:
        raise CorpusPreparationError("corpus_id is invalid")
    documents = _documents(selection.get("documents"))
    return {
        "schema_version": CORPUS_MANIFEST_SCHEMA_VERSION,
        "mission_id": mission_id,
        "corpus_id": corpus_id.strip(),
        "material": material,
        "trust_status": "human_reviewed_authorized_corpus_manifest_not_evaluation_result",
        "access_boundary": "institutional_access_local_review_only_no_fulltext_redistribution",
        "documents": documents,
    }


def corpus_selection_template_from_zotero_candidates(
    *, mission_id: str, material: str, corpus_id: str, query: str,
    candidates: tuple[PaperCandidate, ...],
) -> dict[str, Any]:
    """Create a metadata-only *blank* human-review template.

    The template contains no local paths, attachment information, notes, or
    full text. It is intentionally not an authorized corpus manifest: a
    reviewer must make an explicit boolean decision for every candidate before
    it can be converted into one.
    """
    if not all(isinstance(value, str) and value.strip() for value in (mission_id, material, corpus_id, query)):
        raise CorpusPreparationError("selection template identity and query must be nonempty")
    if len(corpus_id) > 120 or not 1 <= len(candidates) <= 250:
        raise CorpusPreparationError("selection template needs between 1 and 250 candidates and a valid corpus_id")
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate.document_id, str) or not candidate.document_id or candidate.document_id in seen:
            raise CorpusPreparationError("selection template candidate identity is invalid or duplicated")
        if not isinstance(candidate.title, str) or not candidate.title.strip() or len(candidate.title) > 500:
            raise CorpusPreparationError("selection template candidate title is invalid")
        seen.add(candidate.document_id)
        cards.append({
            "document_id": candidate.document_id,
            "title": candidate.title.strip(),
            "doi": normalized_doi_or_none(candidate.doi),
            "include_for_corpus": "unreviewed",
            "review_reason": "",
        })
    return {
        "schema_version": CORPUS_SELECTION_TEMPLATE_SCHEMA_VERSION,
        "mission_id": mission_id.strip(),
        "corpus_id": corpus_id.strip(),
        "material": material.strip(),
        "query": query.strip(),
        "candidate_fingerprint": _selection_fingerprint(cards),
        "trust_status": "blank_human_corpus_selection_template_not_manifest",
        "candidates": cards,
    }


def corpus_manifest_from_selection_review(
    *, mission_id: str, material: str, review: object,
) -> dict[str, Any]:
    """Convert a fully reviewed Zotero candidate template into a manifest."""
    _validate_selection_review(review)
    assert isinstance(review, dict)
    if review["mission_id"] != mission_id or review["material"] != material:
        raise CorpusPreparationError("selection review must match the mission identity and material")
    selected = [
        {
            "document_id": item["document_id"],
            "title": item["title"],
            "doi": item["doi"],
            "access_policy": _ACCESS_POLICY,
        }
        for item in review["candidates"] if item["include_for_corpus"]
    ]
    return corpus_manifest_from_review(
        mission_id=mission_id,
        material=material,
        selection={"corpus_id": review["corpus_id"], "material": material, "documents": selected},
    )


def write_corpus_selection_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_selection_template(template)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "corpus_selection_template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def candidates_from_authorized_corpus_manifest(
    manifest: dict[str, Any], query: str
) -> tuple[PaperCandidate, ...]:
    """Seed eligible local candidates from an explicit reviewed corpus only.

    These cards preserve provenance and access authorization, but deliberately
    carry no ranking score and must not be presented as a retrieval result.
    """
    _validate_manifest(manifest)
    if not isinstance(query, str) or not query.strip():
        raise CorpusPreparationError("candidate seeding requires a nonempty mission question")
    return tuple(
        PaperCandidate(
            document_id=item["document_id"],
            title=item["title"],
            query=query,
            source="Authorized local corpus manifest",
            publication_year=None,
            locator_hint="metadata:reviewed-corpus-manifest",
            score=None,
            is_content_accessible=True,
            doi=normalized_doi_or_none(item["doi"]),
        )
        for item in manifest["documents"]
    )


def write_corpus_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    _validate_manifest(manifest)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "corpus_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_corpus_manifest(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CorpusPreparationError("corpus_manifest.json is invalid JSON") from error
    _validate_manifest(payload)
    if payload["mission_id"] != mission_id:
        raise CorpusPreparationError("corpus manifest does not belong to mission")
    return payload


def gold_standard_template_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Create blank human annotation slots; do not imply measured performance."""
    _validate_manifest(manifest)
    return {
        "schema_version": GOLD_STANDARD_TEMPLATE_SCHEMA_VERSION,
        "mission_id": manifest["mission_id"],
        "corpus_id": manifest["corpus_id"],
        "trust_status": "blank_human_annotation_template_not_evaluation_result",
        "annotation_instructions": {
            "retrieval_relevance": "Mark relevant, partially_relevant, or not_relevant after reading the authorized paper.",
            "evidence_annotations": "Record only reviewer-selected evidence IDs, locators, and correctness judgments; do not paste unrestricted full text.",
            "material_fact_annotations": "Record fact IDs and field-level correctness after local comparison with the authorized source.",
            "comparison_annotations": "Mark whether paired evidence is comparable under stated conditions; do not turn a comparison into a conclusion.",
            "gap_annotations": "For every candidate, judge evidence completeness, novelty review status, and actionability; candidate status is not a scientific finding.",
        },
        "documents": [
            {
                "document_id": item["document_id"],
                "retrieval_relevance": "unreviewed",
                "evidence_annotations": [],
                "material_fact_annotations": [],
                "comparison_annotations": [],
                "gap_annotations": [],
            }
            for item in manifest["documents"]
        ],
    }


def write_gold_standard_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_template(template)
    path = run_dir / "human_gold_standard_template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _documents(raw: object) -> list[dict[str, str | None]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 250:
        raise CorpusPreparationError("corpus must contain between 1 and 250 explicit documents")
    result: list[dict[str, str | None]] = []
    document_ids: set[str] = set()
    normalized_dois: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != _DOCUMENT_FIELDS:
            raise CorpusPreparationError("corpus document fields are invalid; local paths and attachment metadata are prohibited")
        document_id = item.get("document_id")
        title = item.get("title")
        doi = item.get("doi")
        policy = item.get("access_policy")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 180 or document_id in document_ids:
            raise CorpusPreparationError("corpus document_id is invalid or duplicated")
        if not isinstance(title, str) or not title.strip() or len(title) > 500:
            raise CorpusPreparationError("corpus title is invalid")
        normalized_doi = normalized_doi_or_none(doi)
        if doi is not None and (not isinstance(doi, str) or not doi.strip() or len(doi) > 300 or normalized_doi is None):
            raise CorpusPreparationError("corpus DOI must be a syntactically valid nonempty string or null")
        if normalized_doi is not None and normalized_doi in normalized_dois:
            raise CorpusPreparationError("corpus documents must not contain duplicate normalized DOIs")
        if policy != _ACCESS_POLICY:
            raise CorpusPreparationError("corpus documents must be limited to institutionally authorized internal-review access")
        document_ids.add(document_id)
        if normalized_doi is not None:
            normalized_dois.add(normalized_doi)
        result.append({"document_id": document_id, "title": title.strip(), "doi": normalized_doi, "access_policy": policy})
    return result


def _validate_manifest(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
        raise CorpusPreparationError("corpus manifest has unsupported or missing fields")
    if payload.get("schema_version") != CORPUS_MANIFEST_SCHEMA_VERSION:
        raise CorpusPreparationError("corpus manifest schema version is invalid")
    if payload.get("trust_status") != "human_reviewed_authorized_corpus_manifest_not_evaluation_result":
        raise CorpusPreparationError("corpus manifest trust status is invalid")
    if payload.get("access_boundary") != "institutional_access_local_review_only_no_fulltext_redistribution":
        raise CorpusPreparationError("corpus access boundary is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id", "material")):
        raise CorpusPreparationError("corpus manifest identity is invalid")
    _documents(payload.get("documents"))


def _selection_fingerprint(cards: list[dict[str, Any]]) -> str:
    stable = [
        {key: item[key] for key in ("document_id", "title", "doi")}
        for item in cards
    ]
    encoded = json.dumps(stable, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_selection_template(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _SELECTION_TEMPLATE_FIELDS:
        raise CorpusPreparationError("corpus selection template has unsupported or missing fields")
    if payload.get("schema_version") != CORPUS_SELECTION_TEMPLATE_SCHEMA_VERSION:
        raise CorpusPreparationError("corpus selection template schema version is invalid")
    if payload.get("trust_status") != "blank_human_corpus_selection_template_not_manifest":
        raise CorpusPreparationError("corpus selection template trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id", "material", "query", "candidate_fingerprint")):
        raise CorpusPreparationError("corpus selection template identity is invalid")
    cards = _selection_cards(payload.get("candidates"), allow_unreviewed=True)
    if payload["candidate_fingerprint"] != _selection_fingerprint(cards):
        raise CorpusPreparationError("corpus selection template candidate fingerprint is invalid")


def _validate_selection_review(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _SELECTION_TEMPLATE_FIELDS:
        raise CorpusPreparationError("corpus selection review has unsupported or missing fields")
    if payload.get("schema_version") != CORPUS_SELECTION_TEMPLATE_SCHEMA_VERSION:
        raise CorpusPreparationError("corpus selection review schema version is invalid")
    if payload.get("trust_status") != "human_reviewed_corpus_selection_for_manifest":
        raise CorpusPreparationError("corpus selection review requires explicit human review status")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id", "material", "query", "candidate_fingerprint")):
        raise CorpusPreparationError("corpus selection review identity is invalid")
    cards = _selection_cards(payload.get("candidates"), allow_unreviewed=False)
    if payload["candidate_fingerprint"] != _selection_fingerprint(cards):
        raise CorpusPreparationError("corpus selection review does not match its original candidate set")
    if not any(item["include_for_corpus"] for item in cards):
        raise CorpusPreparationError("corpus selection review must include at least one candidate")


def _selection_cards(raw: object, *, allow_unreviewed: bool) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 250:
        raise CorpusPreparationError("corpus selection candidates must contain between 1 and 250 entries")
    cards: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != _SELECTION_CANDIDATE_FIELDS:
            raise CorpusPreparationError("corpus selection candidate fields are invalid")
        document_id, title, doi = item.get("document_id"), item.get("title"), item.get("doi")
        decision, reason = item.get("include_for_corpus"), item.get("review_reason")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 180 or document_id in ids:
            raise CorpusPreparationError("corpus selection document_id is invalid or duplicated")
        if not isinstance(title, str) or not title.strip() or len(title) > 500:
            raise CorpusPreparationError("corpus selection title is invalid")
        if doi is not None and (not isinstance(doi, str) or normalized_doi_or_none(doi) is None):
            raise CorpusPreparationError("corpus selection DOI is invalid")
        if allow_unreviewed:
            if decision != "unreviewed" or reason != "":
                raise CorpusPreparationError("blank selection templates must keep every decision unreviewed")
        elif not isinstance(decision, bool) or not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise CorpusPreparationError("reviewed selection decisions require a boolean and a nonempty reason")
        ids.add(document_id)
        cards.append({
            "document_id": document_id.strip(), "title": title.strip(),
            "doi": normalized_doi_or_none(doi), "include_for_corpus": decision,
            "review_reason": reason if isinstance(reason, str) else "",
        })
    return cards


def _validate_template(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "corpus_id", "trust_status", "annotation_instructions", "documents"}:
        raise CorpusPreparationError("gold-standard template has unsupported or missing fields")
    if payload.get("schema_version") != GOLD_STANDARD_TEMPLATE_SCHEMA_VERSION or payload.get("trust_status") != "blank_human_annotation_template_not_evaluation_result":
        raise CorpusPreparationError("gold-standard template schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id")):
        raise CorpusPreparationError("gold-standard template identity is invalid")
    if not isinstance(payload.get("annotation_instructions"), dict) or not isinstance(payload.get("documents"), list):
        raise CorpusPreparationError("gold-standard template fields are invalid")
    document_ids: set[str] = set()
    for item in payload["documents"]:
        if not isinstance(item, dict) or set(item) != {"document_id", "retrieval_relevance", "evidence_annotations", "material_fact_annotations", "comparison_annotations", "gap_annotations"}:
            raise CorpusPreparationError("gold-standard document fields are invalid")
        if not isinstance(item["document_id"], str) or not item["document_id"] or item["document_id"] in document_ids or item["retrieval_relevance"] != "unreviewed":
            raise CorpusPreparationError("gold-standard document identity or default relevance is invalid")
        if not all(isinstance(item[key], list) and not item[key] for key in ("evidence_annotations", "material_fact_annotations", "comparison_annotations", "gap_annotations")):
            raise CorpusPreparationError("gold-standard template must start with empty annotation lists")
        document_ids.add(item["document_id"])
