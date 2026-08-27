"""Offline, quote-free routing drafts for private PotentialScope review pools.

This module is intentionally weaker than an LLM triage: it uses only a small,
auditable keyword vocabulary to help order local human review.  It never sends
private excerpts anywhere and cannot create evidence, a reviewed registry, a
frozen scope, or an executable calculation task.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


LOCAL_TRIAGE_SCHEMA_VERSION = "1.0"
LOCAL_TRIAGE_TRUST_STATUS = "untrusted_local_keyword_private_potential_scope_source_triage_not_evidence"
LOCAL_BATCH_TEMPLATE_STATUS = "blank_human_batch_local_keyword_triage_decision_template"
_MAX_PROPOSALS = 12
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "potential_model_scope": ("potential", "force field", "interatomic", "deep potential", "machine learning potential", "mlip"),
    "training_boundary": ("training", "trained", "dataset", "data set", "labeling", "labelled"),
    "known_limitation": ("limitation", "challenge", "failure", "fail", "inaccur", "discrepan", "deviation"),
    "reference_method": ("dft", "density functional", "first-principles", "ab initio", "reference calculation"),
    "condition_axis": ("strain", "temperature", "pressure", "defect", "vacan", "interface", "thickness", "composition"),
    "phase_structure": ("phase", "structure", "crystal", "polymorph", "symmetry", "lattice"),
    "magnetic_boundary": ("magnetic", "magnet", "spin", "antiferromag", "ferromag"),
    "finite_temperature": ("temperature", "thermal", "finite-temperature", "finite temperature"),
}


class PotentialScopeLocalTriageError(ValueError):
    """Raised when an offline routing draft would cross a review boundary."""


def build_local_keyword_triage(pool: object) -> dict[str, Any]:
    """Return at most twelve low-confidence, quote-free routing suggestions."""
    normalized = _pool(pool)
    rows: list[tuple[int, str, list[str]]] = []
    for candidate in normalized["candidate_segments"]:
        text = candidate["quote"].casefold()
        roles = sorted(role for role, terms in _ROLE_KEYWORDS.items() if any(term in text for term in terms))
        if roles:
            rows.append((len(roles), candidate["segment_id"], roles))
    rows.sort(key=lambda row: (-row[0], row[1]))
    proposals = [
        {
            "segment_id": segment_id,
            "roles": roles,
            "reason": "Local keyword routing match only; human relevance and provenance review required.",
            "confidence": min(0.45, round(0.18 + 0.05 * len(roles), 4)),
        }
        for _, segment_id, roles in rows[:_MAX_PROPOSALS]
    ]
    if not proposals:
        raise PotentialScopeLocalTriageError("local keyword routing found no eligible candidate segments")
    draft = {
        "schema_version": LOCAL_TRIAGE_SCHEMA_VERSION,
        "mission_id": normalized["mission_id"],
        "document_id": normalized["document_id"],
        "trust_status": LOCAL_TRIAGE_TRUST_STATUS,
        "source_markdown_sha256": normalized["source_markdown_sha256"],
        "task_id_sha256": normalized["task_id_sha256"],
        "router": "local-deterministic-keyword-router",
        "proposals": proposals,
        "review_boundary": (
            "This offline routing draft contains only private segment identifiers and generic routing labels. It is not "
            "evidence, a material fact, a potential-model conclusion, or permission to execute a calculation. A "
            "researcher must inspect the private source and make a new, explicit selection decision."
        ),
    }
    _validate_draft(draft)
    return draft


def build_local_batch_review_template(*, mission_id: str, drafts: object) -> dict[str, Any]:
    """Create a blank, non-projecting decision sheet for local routing drafts."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(drafts, list) or not drafts:
        raise PotentialScopeLocalTriageError("local triage batch inputs are invalid")
    documents: set[str] = set()
    rows: list[dict[str, str]] = []
    for draft in drafts:
        _validate_draft(draft)
        if draft["mission_id"] != mission_id or draft["document_id"] in documents:
            raise PotentialScopeLocalTriageError("local triage batch has inconsistent document identities")
        documents.add(draft["document_id"])
        rows.append({
            "document_id": draft["document_id"],
            "triage_sha256": _sha(draft),
            "decision": "",
            "note": "",
        })
    return {
        "schema_version": LOCAL_TRIAGE_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": LOCAL_BATCH_TEMPLATE_STATUS,
        "reviewer": "",
        "reviewed_at": "",
        "documents": sorted(rows, key=lambda row: row["document_id"]),
        "review_boundary": (
            "This blank sheet only records whether a reviewer wants to inspect or dismiss a local keyword-routing "
            "suggestion. It cannot approve a source-map selection, create a reviewed-source registry, or authorize "
            "scientific claims or calculation execution."
        ),
    }


def write_once(path: Path, payload: object) -> Path:
    """Write a JSON artifact once, never inside a CosMatter run directory."""
    if path.suffix.casefold() != ".json" or "runs" in {part.casefold() for part in path.parts} or path.exists():
        raise PotentialScopeLocalTriageError("local triage output must be a new JSON file outside CosMatter/runs")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeLocalTriageError("local triage output cannot be written") from error
    return path


def _pool(pool: object) -> dict[str, Any]:
    if not isinstance(pool, dict):
        raise PotentialScopeLocalTriageError("private review pool is invalid")
    required = {"mission_id", "document_id", "task_id_sha256", "source_markdown_sha256", "candidate_segments"}
    if not required <= set(pool) or not all(isinstance(pool.get(key), str) and pool[key].strip() for key in required - {"candidate_segments"}):
        raise PotentialScopeLocalTriageError("private review pool identity is invalid")
    candidates = pool["candidate_segments"]
    if not isinstance(candidates, list) or not candidates:
        raise PotentialScopeLocalTriageError("private review pool candidates are invalid")
    for candidate in candidates:
        if not isinstance(candidate, dict) or not all(isinstance(candidate.get(key), str) and candidate[key].strip() for key in ("segment_id", "quote")):
            raise PotentialScopeLocalTriageError("private review pool candidate is invalid")
    return pool


def _validate_draft(draft: object) -> None:
    expected = {"schema_version", "mission_id", "document_id", "trust_status", "source_markdown_sha256", "task_id_sha256", "router", "proposals", "review_boundary"}
    if not isinstance(draft, dict) or set(draft) != expected or draft.get("schema_version") != LOCAL_TRIAGE_SCHEMA_VERSION or draft.get("trust_status") != LOCAL_TRIAGE_TRUST_STATUS:
        raise PotentialScopeLocalTriageError("local triage draft schema is invalid")
    if not all(isinstance(draft.get(key), str) and draft[key].strip() for key in ("mission_id", "document_id", "source_markdown_sha256", "task_id_sha256", "router", "review_boundary")):
        raise PotentialScopeLocalTriageError("local triage draft identity is invalid")
    proposals = draft.get("proposals")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= _MAX_PROPOSALS:
        raise PotentialScopeLocalTriageError("local triage proposals are invalid")
    seen: set[str] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict) or set(proposal) != {"segment_id", "roles", "reason", "confidence"}:
            raise PotentialScopeLocalTriageError("local triage proposal fields are invalid")
        if not isinstance(proposal["segment_id"], str) or not proposal["segment_id"] or proposal["segment_id"] in seen:
            raise PotentialScopeLocalTriageError("local triage proposal identifier is invalid")
        if not isinstance(proposal["roles"], list) or not proposal["roles"] or not all(isinstance(role, str) for role in proposal["roles"]):
            raise PotentialScopeLocalTriageError("local triage proposal roles are invalid")
        if not isinstance(proposal["reason"], str) or not proposal["reason"].strip() or len(proposal["reason"]) > 300:
            raise PotentialScopeLocalTriageError("local triage proposal rationale is invalid")
        if not isinstance(proposal["confidence"], (int, float)) or isinstance(proposal["confidence"], bool) or not 0 <= float(proposal["confidence"]) <= 1:
            raise PotentialScopeLocalTriageError("local triage proposal confidence is invalid")
        seen.add(proposal["segment_id"])


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
