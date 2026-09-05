#!/usr/bin/env python3
"""Send one bounded private BFO shortlist to DeepSeek for an untrusted value draft."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path

from cosmatter.config import Settings
from cosmatter.deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from cosmatter.material_indicator_draft import (
    MaterialIndicatorDraftError,
    combine_untrusted_indicator_value_drafts,
    indicator_value_draft_prompts,
    untrusted_indicator_value_draft,
)
from cosmatter.material_indicator_registry import load_material_indicator_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL = "deepseek-v4-flash"


def _outside_project(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT in resolved.parents:
        raise MaterialIndicatorDraftError("private shortlist and draft output must remain outside the repository")
    if "runs" in {part.casefold() for part in resolved.parts}:
        raise MaterialIndicatorDraftError("private shortlist and draft output must remain outside a runs directory")
    return resolved


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterialIndicatorDraftError(f"{label} is not valid UTF-8 JSON") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortlist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--allow-private-content-to-deepseek", action="store_true")
    parser.add_argument("--segments-per-request", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--disable-thinking", action="store_true", help="disable reasoning mode for bounded extraction only")
    args = parser.parse_args()
    if not args.allow_private_content_to_deepseek:
        raise SystemExit("refusing to transmit private excerpts: pass --allow-private-content-to-deepseek after authorization")
    try:
        shortlist_path = _outside_project(args.shortlist)
        output_path = _outside_project(args.output)
        if output_path.suffix.casefold() != ".json" or output_path.exists():
            raise MaterialIndicatorDraftError("private indicator draft output must be a new .json file")
        shortlist = _read_json(shortlist_path, "private indicator shortlist")
        catalog = load_material_indicator_catalog(PROJECT_ROOT / "configs" / "bfo_p0_material_indicator_catalog.json")
        if args.env_file is None:
            # Preserve Settings.load's protected workspace .env lookup. Passing
            # an explicit mapping intentionally creates a hermetic test config.
            settings = Settings.load()
        else:
            environment = dict(os.environ)
            environment["COSMATTER_ENV_FILE"] = str(args.env_file)
            settings = Settings.load(environment)
        if settings.llm_provider != "deepseek" or settings.llm_model != EXPECTED_MODEL:
            raise MaterialIndicatorDraftError("this controlled run requires configured model deepseek-v4-flash")
        if args.disable_thinking:
            settings = replace(settings, llm_thinking_enabled=False, llm_reasoning_effort=None)
        settings = replace(settings, api_max_retries=1)
        # Each excerpt is transmitted exactly once. Smaller batches avoid a
        # long structured response timing out while preserving the same global
        # 12-segment authorization boundary.
        documents = shortlist.get("documents") if isinstance(shortlist, dict) else None
        if not isinstance(documents, list) or not documents:
            raise MaterialIndicatorDraftError("private indicator shortlist has no documents")
        units = []
        for document in documents:
            if not isinstance(document, dict) or not isinstance(document.get("segments"), list):
                raise MaterialIndicatorDraftError("private indicator shortlist document segments are invalid")
            for segment in document["segments"]:
                units.append({**document, "segments": [segment]})
        batches = [units[index:index + args.segments_per_request] for index in range(0, len(units), args.segments_per_request)]
        drafts = []
        for batch_documents in batches:
            batch_shortlist = {
                **shortlist,
                "documents": batch_documents,
                "document_count": len(batch_documents),
                "segment_count": sum(len(item.get("segments", [])) for item in batch_documents if isinstance(item, dict)),
            }
            system_prompt, user_prompt = indicator_value_draft_prompts(batch_shortlist, catalog)
            completion = DeepSeekAdapter(settings).draft(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2_500,
                json_object=True,
                thinking_enabled=False if args.disable_thinking else None,
            )
            if completion.model != EXPECTED_MODEL:
                raise MaterialIndicatorDraftError("provider returned a different model than deepseek-v4-flash")
            drafts.append(
                untrusted_indicator_value_draft(
                    shortlist=batch_shortlist,
                    catalog=catalog,
                    completion=completion,
                    drop_invalid_facts=True,
                )
            )
        draft = combine_untrusted_indicator_value_drafts(drafts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (MaterialIndicatorDraftError, DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
        raise SystemExit(f"private BFO indicator draft failed safely: {error}") from error
    print(
        json.dumps(
            {
                "status": "untrusted_private_indicator_value_draft_created",
                "model": draft["model"],
                "provider_batch_count": draft["provider_batch_count"],
                "fact_count": len(draft["facts"]),
                "rejected_fact_count": draft["rejected_fact_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
