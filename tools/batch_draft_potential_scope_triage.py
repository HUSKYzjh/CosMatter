"""Create automatic private triage drafts for every document in one review index.

This is deliberately an opt-in, sequential client: it sends bounded private
candidate excerpts to DeepSeek only after the caller supplies the consent
flag.  Each successful document yields a quote-free untrusted draft; a failed
provider call is reported separately and never becomes a reviewed source.
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
    parser = argparse.ArgumentParser(description="Batch-create untrusted private PotentialScope triage drafts.")
    parser.add_argument("--review-index", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--env-file", type=Path, help="optional explicit dotenv file")
    parser.add_argument("--max-documents", type=int, default=48, help="safe cap from 1 through 200")
    parser.add_argument("--continue-existing", action="store_true", help="skip existing .triage.json outputs")
    parser.add_argument("--allow-private-content-to-deepseek", action="store_true", help="required consent to transmit private excerpts")
    args = parser.parse_args()
    if not args.allow_private_content_to_deepseek:
        raise SystemExit("refusing to transmit private excerpts: pass --allow-private-content-to-deepseek after review")
    if not 1 <= args.max_documents <= 200 or not _outside_runs(args.review_index) or not _outside_runs(args.output_directory):
        raise SystemExit("invalid document cap or a private input/output is inside CosMatter/runs")
    try:
        index = json.loads(args.review_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read private review index: {error}") from error
    entries = index.get("entries") if isinstance(index, dict) else None
    mission_id = index.get("mission_id") if isinstance(index, dict) else None
    if index.get("trust_status") != "private_unreviewed_potential_scope_p0_review_index_not_evidence" or not isinstance(mission_id, str) or not mission_id or not isinstance(entries, list):
        raise SystemExit("private review index is invalid")
    environment = dict(os.environ)
    if args.env_file is not None:
        environment["COSMATTER_ENV_FILE"] = str(args.env_file)
    try:
        adapter = DeepSeekAdapter(Settings.load(environment))
    except DeepSeekConfigurationError as error:
        raise SystemExit(f"DeepSeek is not configured: {error}") from error
    args.output_directory.mkdir(parents=True, exist_ok=True)
    completed: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []
    for entry in entries[: args.max_documents]:
        document_id = entry.get("document_id") if isinstance(entry, dict) else None
        markdown_hash = entry.get("markdown_sha256") if isinstance(entry, dict) else None
        pool_name = entry.get("pool_filename") if isinstance(entry, dict) else None
        if not isinstance(document_id, str) or not isinstance(markdown_hash, str) or not isinstance(pool_name, str) or Path(pool_name).name != pool_name:
            failed.append({"document_id": document_id if isinstance(document_id, str) else "unknown", "reason": "invalid_private_index_entry"})
            continue
        output = args.output_directory / f"{document_id}.triage.json"
        if output.exists() and args.continue_existing:
            skipped.append(document_id)
            continue
        if output.exists():
            failed.append({"document_id": document_id, "reason": "output_exists"})
            continue
        task = {"document_id": document_id, "provider": "mineru", "state": "done", "task_id": "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest()}
        try:
            pool = load_private_pool(path=args.review_index.parent / pool_name, mission_id=mission_id, document_id=document_id, source_task=task)
            system_prompt, user_prompt = potential_scope_triage_prompts(pool)
            completion = adapter.draft(system_prompt=system_prompt, user_prompt=user_prompt)
            draft = untrusted_triage_from_completion(pool=pool, completion=completion)
            write_untrusted_triage_draft(output, draft)
            completed.append(document_id)
        except (PotentialScopeAutoTriageError, DeepSeekRequestError, DeepSeekConfigurationError) as error:
            failed.append({"document_id": document_id, "reason": type(error).__name__})
    print(json.dumps({"status": "batch_private_triage_finished", "completed_document_ids": completed, "skipped_document_ids": skipped, "failed": failed, "trust_status": "untrusted_llm_private_potential_scope_source_triage_not_evidence"}, ensure_ascii=False))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
