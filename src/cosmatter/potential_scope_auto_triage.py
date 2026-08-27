"""Private, untrusted LLM triage for PotentialScope literature review pools.

This module narrows a private MinerU candidate pool into a *suggested* set of
segments relevant to a potential-model applicability study.  It deliberately
does not create a Source Map, EvidenceCard, reviewed-source registry, frozen
scope, or executable calculation task.  A researcher must still approve a
batch before its suggestions can enter the existing human-review workflow.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .deepseek import DraftCompletion
from .mineru_local_review import MinerULocalReviewError, load_mineru_markdown_review_pool


POTENTIAL_SCOPE_TRIAGE_SCHEMA_VERSION = "1.0"
_MAX_PROPOSALS = 12
_ROLES = {
    "potential_model_scope",
    "training_boundary",
    "known_limitation",
    "reference_method",
    "condition_axis",
    "phase_structure",
    "magnetic_boundary",
    "finite_temperature",
    "not_useful",
}


class PotentialScopeAutoTriageError(ValueError):
    """Raised when a private LLM triage draft is malformed or unsafe."""


def potential_scope_triage_prompts(pool: object) -> tuple[str, str]:
    """Return bounded prompts for a private, non-evidentiary segment triage.

    Quotes are sent only in the returned user prompt.  Callers must obtain an
    explicit user consent before transmitting this prompt to an LLM provider.
    """
    normalized = _pool(pool)
    system = (
        "You triage private material-science literature excerpts for a potential-model "
        "applicability study. Return JSON only. Do not make scientific conclusions, "
        "do not invent citations or segment identifiers, and do not quote any excerpt. "
        "Select at most 12 supplied segments. Each selection may have one or more roles "
        "from the supplied allow-list. Your output is an untrusted routing suggestion, "
        "not evidence and not a research conclusion."
    )
    candidates = [
        {
            "segment_id": item["segment_id"],
            "locator": item["locator"],
            "kind": item["kind"],
            "private_excerpt": item["quote"],
        }
        for item in normalized["candidate_segments"]
    ]
    user = json.dumps(
        {
            "document_id": normalized["document_id"],
            "allowed_roles": sorted(_ROLES),
            "maximum_selected_segments": _MAX_PROPOSALS,
            "candidate_segments": candidates,
            "required_json_schema": {
                "document_id": normalized["document_id"],
                "proposals": [
                    {
                        "segment_id": "one supplied identifier",
                        "roles": ["one or more allowed roles"],
                        "reason": "brief routing rationale, maximum 300 characters",
                        "confidence": "number from 0 to 1",
                    }
                ],
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(system) > 8_000 or len(user) > 20_000:
        raise PotentialScopeAutoTriageError("private triage prompt exceeds the configured LLM boundary")
    return system, user


def untrusted_triage_from_completion(*, pool: object, completion: DraftCompletion) -> dict[str, Any]:
    """Parse a completion into a quote-free, untrusted private routing draft."""
    normalized = _pool(pool)
    if not isinstance(completion, DraftCompletion) or not completion.content.strip():
        raise PotentialScopeAutoTriageError("LLM completion is invalid")
    payload = _json_object(completion.content)
    if set(payload) != {"document_id", "proposals"} or payload.get("document_id") != normalized["document_id"]:
        raise PotentialScopeAutoTriageError("LLM triage completion has an invalid document identity")
    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= _MAX_PROPOSALS:
        raise PotentialScopeAutoTriageError("LLM triage completion must contain one through twelve proposals")
    available = {item["segment_id"] for item in normalized["candidate_segments"]}
    selected: set[str] = set()
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        if not isinstance(proposal, dict) or set(proposal) != {"segment_id", "roles", "reason", "confidence"}:
            raise PotentialScopeAutoTriageError("LLM triage proposal has unsupported or missing fields")
        segment_id = proposal.get("segment_id")
        roles = proposal.get("roles")
        reason = proposal.get("reason")
        confidence = proposal.get("confidence")
        if not isinstance(segment_id, str) or segment_id not in available or segment_id in selected:
            raise PotentialScopeAutoTriageError("LLM triage proposal segment identifier is invalid")
        if not isinstance(roles, list) or not roles or len(roles) > len(_ROLES) or any(role not in _ROLES for role in roles):
            raise PotentialScopeAutoTriageError("LLM triage proposal roles are invalid")
        if len(set(roles)) != len(roles) or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 300:
            raise PotentialScopeAutoTriageError("LLM triage proposal reason is invalid")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
            raise PotentialScopeAutoTriageError("LLM triage proposal confidence is invalid")
        selected.add(segment_id)
        rows.append(
            {
                "segment_id": segment_id,
                "roles": sorted(roles),
                "reason": reason.strip(),
                "confidence": round(float(confidence), 4),
            }
        )
    result = {
        "schema_version": POTENTIAL_SCOPE_TRIAGE_SCHEMA_VERSION,
        "mission_id": normalized["mission_id"],
        "document_id": normalized["document_id"],
        "trust_status": "untrusted_llm_private_potential_scope_source_triage_not_evidence",
        "source_markdown_sha256": normalized["source_markdown_sha256"],
        "task_id_sha256": normalized["task_id_sha256"],
        "model": completion.model.strip() if isinstance(completion.model, str) and completion.model.strip() else "unknown",
        "request_id": completion.request_id if isinstance(completion.request_id, str) and completion.request_id.strip() else None,
        "proposals": sorted(rows, key=lambda item: item["segment_id"]),
        "review_boundary": (
            "An LLM selected these private candidate identifiers for routing only. A researcher must review and "
            "approve the batch before any selected excerpt can become a source-map selection. This is not evidence, "
            "a material fact, a potential-model conclusion, or permission to execute a calculation."
        ),
    }
    _validate_triage(result)
    return result


def load_private_pool(*, path: Path, mission_id: str, document_id: str, source_task: object) -> dict[str, Any]:
    """Load a pool through its recorded MinerU task binding."""
    try:
        return load_mineru_markdown_review_pool(
            path=path, mission_id=mission_id, document_id=document_id, source_task=source_task
        )
    except MinerULocalReviewError as error:
        raise PotentialScopeAutoTriageError("private review pool cannot be safely loaded") from error


def write_untrusted_triage_draft(path: Path, draft: object) -> Path:
    """Write a quote-free triage draft once, outside a run directory."""
    _validate_triage(draft)
    if path.suffix.casefold() != ".json":
        raise PotentialScopeAutoTriageError("triage output must use a .json filename")
    if "runs" in {part.casefold() for part in path.parts}:
        raise PotentialScopeAutoTriageError("private triage output must remain outside CosMatter/runs")
    if path.exists():
        raise PotentialScopeAutoTriageError("triage output already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeAutoTriageError("triage output cannot be written") from error
    return path


def _pool(pool: object) -> dict[str, Any]:
    if not isinstance(pool, dict):
        raise PotentialScopeAutoTriageError("private review pool is invalid")
    required = {"mission_id", "document_id", "task_id_sha256", "source_markdown_sha256", "candidate_segments"}
    if not required <= set(pool):
        raise PotentialScopeAutoTriageError("private review pool is missing required fields")
    if not all(isinstance(pool.get(key), str) and pool[key].strip() for key in required - {"candidate_segments"}):
        raise PotentialScopeAutoTriageError("private review pool identity is invalid")
    candidates = pool.get("candidate_segments")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 48:
        raise PotentialScopeAutoTriageError("private review pool candidates are invalid")
    for item in candidates:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("segment_id", "locator", "kind", "quote")):
            raise PotentialScopeAutoTriageError("private review pool candidate is invalid")
    return pool


def _json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        first_break = text.find("\n")
        if first_break < 0 or not text.endswith("```"):
            raise PotentialScopeAutoTriageError("LLM triage completion is not valid JSON")
        text = text[first_break + 1 : -3].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise PotentialScopeAutoTriageError("LLM triage completion is not valid JSON") from error
    if not isinstance(payload, dict):
        raise PotentialScopeAutoTriageError("LLM triage completion must be a JSON object")
    return payload


def _validate_triage(payload: object) -> None:
    expected = {
        "schema_version", "mission_id", "document_id", "trust_status", "source_markdown_sha256", "task_id_sha256",
        "model", "request_id", "proposals", "review_boundary",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeAutoTriageError("triage draft has unsupported or missing fields")
    if payload.get("schema_version") != POTENTIAL_SCOPE_TRIAGE_SCHEMA_VERSION or payload.get("trust_status") != "untrusted_llm_private_potential_scope_source_triage_not_evidence":
        raise PotentialScopeAutoTriageError("triage draft schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "source_markdown_sha256", "task_id_sha256", "model", "review_boundary")):
        raise PotentialScopeAutoTriageError("triage draft identity is invalid")
    if payload.get("request_id") is not None and (not isinstance(payload["request_id"], str) or not payload["request_id"].strip()):
        raise PotentialScopeAutoTriageError("triage request identifier is invalid")
    rows = payload.get("proposals")
    if not isinstance(rows, list) or not 1 <= len(rows) <= _MAX_PROPOSALS:
        raise PotentialScopeAutoTriageError("triage draft proposals are invalid")
    identifiers: set[str] = set()
    for item in rows:
        if not isinstance(item, dict) or set(item) != {"segment_id", "roles", "reason", "confidence"}:
            raise PotentialScopeAutoTriageError("triage draft proposal fields are invalid")
        if not isinstance(item.get("segment_id"), str) or not item["segment_id"] or item["segment_id"] in identifiers:
            raise PotentialScopeAutoTriageError("triage draft proposal identifiers are invalid")
        identifiers.add(item["segment_id"])
        if not isinstance(item.get("roles"), list) or not item["roles"] or any(role not in _ROLES for role in item["roles"]):
            raise PotentialScopeAutoTriageError("triage draft proposal roles are invalid")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip() or len(item["reason"]) > 300:
            raise PotentialScopeAutoTriageError("triage draft proposal reason is invalid")
        if not isinstance(item.get("confidence"), (int, float)) or isinstance(item["confidence"], bool) or not 0 <= float(item["confidence"]) <= 1:
            raise PotentialScopeAutoTriageError("triage draft proposal confidence is invalid")
