"""LLM-assisted planning drafts that remain outside evidence and release gates."""

from __future__ import annotations

import json
from pathlib import Path

from .deepseek import DraftCompletion
from .models import MissionBrief


def research_planning_prompts(mission: MissionBrief) -> tuple[str, str]:
    """Build a metadata-only prompt that requests bounded search suggestions."""
    system_prompt = (
        "You are the CosMatter research-planning station. Produce an untrusted JSON draft with "
        "subquestions, bounded search queries, and counterevidence queries. Do not claim any "
        "scientific fact, invent citations, request full text, or write a final conclusion."
    )
    user_prompt = json.dumps(
        {
            "question": mission.question,
            "material": mission.material,
            "property_name": mission.property_name,
            "scope": mission.scope,
            "source_policy": mission.source_policy.value,
            "limits": {"max_subquestions": 5, "max_queries": 8, "max_counterevidence_queries": 4},
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def write_untrusted_plan_draft(run_dir: Path, completion: DraftCompletion) -> Path:
    """Persist the LLM result as a draft that must be reviewed before execution."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "research_plan_draft.json"
    payload = {
        "schema_version": "1.0",
        "trust_status": "untrusted_draft",
        "model": completion.model,
        "content": completion.content,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
