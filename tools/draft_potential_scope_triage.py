"""Call DeepSeek once to triage one private PotentialScope MinerU review pool.

This command deliberately requires a consent flag because its bounded private
excerpts are sent to DeepSeek.  It writes only a quote-free, untrusted routing
draft and never creates evidence, a source map, or an execution task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cosmatter.config import Settings
from cosmatter.deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from cosmatter.potential_scope_auto_triage import (
    PotentialScopeAutoTriageError,
    load_private_pool,
    potential_scope_triage_prompts,
    untrusted_triage_from_completion,
    write_untrusted_triage_draft,
)


def _outside_runs(path: Path) -> bool:
    return "runs" not in {part.casefold() for part in path.parts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one untrusted private PotentialScope LLM triage draft.")
    parser.add_argument("--review-index", required=True, type=Path, help="private review_pool_index.json")
    parser.add_argument("--document-id", required=True, help="document identifier from the private index")
    parser.add_argument("--output", required=True, type=Path, help="new quote-free triage JSON outside CosMatter/runs")
    parser.add_argument("--env-file", type=Path, help="optional explicit dotenv file; defaults to the configured local environment")
    parser.add_argument(
        "--allow-private-content-to-deepseek",
        action="store_true",
        help="required consent: send this private bounded review pool to DeepSeek",
    )
    args = parser.parse_args()
    if not args.allow_private_content_to_deepseek:
        raise SystemExit("refusing to transmit private excerpts: pass --allow-private-content-to-deepseek after review")
    if not _outside_runs(args.review_index) or not _outside_runs(args.output):
        raise SystemExit("private review index and triage output must remain outside CosMatter/runs")
    try:
        index = json.loads(args.review_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read private review index: {error}") from error
    entries = index.get("entries") if isinstance(index, dict) else None
    mission_id = index.get("mission_id") if isinstance(index, dict) else None
    if not isinstance(entries, list) or not isinstance(mission_id, str) or not mission_id:
        raise SystemExit("private review index is invalid")
    entry = next((item for item in entries if isinstance(item, dict) and item.get("document_id") == args.document_id), None)
    if entry is None:
        raise SystemExit("requested document is not present in the private review index")
    markdown_hash = entry.get("markdown_sha256")
    pool_name = entry.get("pool_filename")
    if not isinstance(markdown_hash, str) or not isinstance(pool_name, str) or Path(pool_name).name != pool_name:
        raise SystemExit("private review index entry is invalid")
    source_task = {
        "document_id": args.document_id,
        "provider": "mineru",
        "state": "done",
        "task_id": "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest(),
    }
    try:
        pool = load_private_pool(
            path=args.review_index.parent / pool_name,
            mission_id=mission_id,
            document_id=args.document_id,
            source_task=source_task,
        )
        system_prompt, user_prompt = potential_scope_triage_prompts(pool)
        environment = dict(os.environ)
        if args.env_file is not None:
            environment["COSMATTER_ENV_FILE"] = str(args.env_file)
        completion = DeepSeekAdapter(Settings.load(environment)).draft(
            system_prompt=system_prompt, user_prompt=user_prompt
        )
        draft = untrusted_triage_from_completion(pool=pool, completion=completion)
        write_untrusted_triage_draft(args.output, draft)
    except (PotentialScopeAutoTriageError, DeepSeekConfigurationError, DeepSeekRequestError) as error:
        raise SystemExit(f"private PotentialScope triage failed safely: {error}") from error
    print(json.dumps({"status": "untrusted_private_triage_created", "document_id": draft["document_id"], "proposal_count": len(draft["proposals"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
