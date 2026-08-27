"""Bounded LLM Research-Gap brainstorming that cannot enter the evidence path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .deepseek import DraftCompletion
from .facilities import DiscrepancyRow
from .models import MissionBrief


class GapDraftingError(ValueError):
    """Raised when the structural input for an untrusted Gap draft is unsafe."""


_TRUST_STATUS = "untrusted_llm_research_gap_draft_not_a_candidate_or_finding"


def research_gap_drafting_prompts(
    mission: MissionBrief,
    rows: Iterable[DiscrepancyRow],
) -> tuple[str, str]:
    """Build a metadata-only prompt from condition-diagnostic rows.

    The prompt deliberately contains neither paper text nor citations.  It may
    suggest alternative explanations and retrieval follow-ups, but cannot
    establish a scientific fact or a report-ready Research Gap.
    """
    normalized = _validate_rows(rows)
    system_prompt = (
        "You are the CosMatter Research-Gap drafting station. Return an untrusted JSON brainstorming draft only. "
        "Use only the supplied structural discrepancy rows and evidence identifiers. Propose alternative explanations, "
        "counterevidence retrieval questions, and falsifiable validation ideas. Do not state a scientific finding, "
        "claim a literature gap, claim novelty, invent paper metadata or citations, merge evidence, or produce a final "
        "Research Gap candidate. Every suggestion must explicitly be framed as requiring human review and evidence matching."
    )
    user_prompt = json.dumps(
        {
            "mission": {
                "material": mission.material,
                "property_name": mission.property_name,
                "scope": mission.scope,
            },
            "output_schema": {
                "draft_items": [
                    {
                        "row_index": "1-based supplied row index",
                        "evidence_ids": ["only IDs from that row"],
                        "possible_explanations": ["untrusted alternatives, not findings"],
                        "counterevidence_questions": ["bounded retrieval questions"],
                        "falsification_ideas": ["ways to reject a possible explanation"],
                        "required_human_checks": ["evidence matching and review checks"],
                    }
                ],
                "limitations": ["why this draft cannot be a Research Gap candidate or scientific conclusion"],
            },
            "structural_discrepancy_rows": normalized,
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def write_untrusted_research_gap_draft(
    run_dir: Path,
    mission: MissionBrief,
    completion: DraftCompletion,
    rows: Iterable[DiscrepancyRow],
) -> Path:
    """Persist opaque model output locally, separate from candidate artifacts."""
    normalized = _validate_rows(rows)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "research_gap_draft.json"
    payload = {
        "schema_version": "1.0",
        "mission_id": mission.mission_id,
        "trust_status": _TRUST_STATUS,
        "model": completion.model,
        "input_summary": {
            "condition_row_count": len(normalized),
            "evidence_id_count": len({evidence_id for row in normalized for evidence_id in row["evidence_ids"]}),
        },
        "content": completion.content,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_rows(rows: Iterable[DiscrepancyRow]) -> list[dict[str, object]]:
    source = tuple(rows)
    if not 1 <= len(source) <= 12:
        raise GapDraftingError("Research-Gap drafting requires 1 to 12 discrepancy rows")
    normalized: list[dict[str, object]] = []
    for row in source:
        if not isinstance(row, DiscrepancyRow):
            raise GapDraftingError("Research-Gap drafting requires discrepancy rows")
        values = (*row.supporting_evidence_ids, *row.contradicting_evidence_ids)
        if (
            not isinstance(row.condition_cluster, str)
            or not row.condition_cluster.strip()
            or not row.differing_fields
            or len(row.differing_fields) > 12
            or len(values) < 2
            or len(values) > 24
            or len(set(values)) != len(values)
            or any(not isinstance(value, str) or not value.strip() or len(value) > 160 for value in values)
            or any(not isinstance(value, str) or not value.strip() or len(value) > 120 for value in row.differing_fields)
        ):
            raise GapDraftingError("Research-Gap discrepancy row is invalid")
        normalized.append(
            {
                "condition_cluster": row.condition_cluster.strip(),
                "evidence_ids": list(values),
                "differing_fields": list(row.differing_fields),
                "unknown_fields": list(row.unknown_fields),
            }
        )
    return normalized
