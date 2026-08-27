"""Create or apply a document-level approval batch for PotentialScope triage.

Both actions are local-only.  The command never reads .env, calls DeepSeek,
opens PDFs, or exposes private excerpts.  It turns already-created untrusted
triage drafts into either a concise decision template or a quote-free source
registry after a human records document-level decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cosmatter.potential_scope_batch_approval import (
    PotentialScopeBatchApprovalError,
    build_batch_approval_template,
    build_registry_from_batch_approval,
    load_completed_batch_approval,
    load_triage_drafts,
    write_batch_approval_template,
    write_batch_outputs,
)


def _outside_runs(path: Path) -> bool:
    return "runs" not in {part.casefold() for part in path.parts}


def _index(path: Path) -> tuple[str, list[dict[str, object]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PotentialScopeBatchApprovalError("private review index cannot be read") from error
    if not isinstance(payload, dict) or payload.get("trust_status") != "private_unreviewed_potential_scope_p0_review_index_not_evidence":
        raise PotentialScopeBatchApprovalError("private review index trust status is invalid")
    mission_id = payload.get("mission_id")
    entries = payload.get("entries")
    if not isinstance(mission_id, str) or not mission_id or not isinstance(entries, list) or not entries or not all(isinstance(item, dict) for item in entries):
        raise PotentialScopeBatchApprovalError("private review index identity is invalid")
    return mission_id, entries


def _draft_paths(directory: Path) -> list[Path]:
    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    if not paths:
        raise PotentialScopeBatchApprovalError("no triage JSON files were found")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or apply a local PotentialScope batch approval.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    template = subcommands.add_parser("template", help="create one blank document-level approval template")
    template.add_argument("--review-index", required=True, type=Path)
    template.add_argument("--triage-directory", required=True, type=Path)
    template.add_argument("--output", required=True, type=Path)
    apply = subcommands.add_parser("apply", help="apply a human-completed template and create quote-free outputs")
    apply.add_argument("--review-index", required=True, type=Path)
    apply.add_argument("--triage-directory", required=True, type=Path)
    apply.add_argument("--approval", required=True, type=Path)
    apply.add_argument("--registry-output", required=True, type=Path)
    apply.add_argument("--audit-output", required=True, type=Path)
    args = parser.parse_args()
    paths = [value for value in vars(args).values() if isinstance(value, Path)]
    if any(not _outside_runs(path) for path in paths):
        raise SystemExit("all private approval inputs and outputs must remain outside CosMatter/runs")
    try:
        mission_id, entries = _index(args.review_index)
        drafts = load_triage_drafts(_draft_paths(args.triage_directory), mission_id=mission_id)
        if args.command == "template":
            output = write_batch_approval_template(args.output, build_batch_approval_template(mission_id=mission_id, drafts=drafts))
            print(json.dumps({"status": "blank_batch_approval_created", "document_count": len(drafts), "output": str(output)}, ensure_ascii=False))
            return 0
        approval = load_completed_batch_approval(args.approval)
        index_by_document = {item.get("document_id"): item for item in entries if isinstance(item.get("document_id"), str)}
        pools: dict[str, Path] = {}
        tasks: dict[str, dict[str, str]] = {}
        for draft in drafts:
            item = index_by_document.get(draft["document_id"])
            if not isinstance(item, dict):
                raise PotentialScopeBatchApprovalError("automated draft is not included in the private review index")
            markdown_hash = item.get("markdown_sha256")
            pool_name = item.get("pool_filename")
            if not isinstance(markdown_hash, str) or not isinstance(pool_name, str) or Path(pool_name).name != pool_name:
                raise PotentialScopeBatchApprovalError("private review index entry is invalid")
            pools[draft["document_id"]] = args.review_index.parent / pool_name
            tasks[draft["document_id"]] = {
                "document_id": draft["document_id"],
                "provider": "mineru",
                "state": "done",
                "task_id": "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest(),
            }
        registry, audit = build_registry_from_batch_approval(mission_id=mission_id, drafts=drafts, approval=approval, pools_by_document=pools, source_tasks_by_document=tasks)
        registry_path, audit_path = write_batch_outputs(registry_path=args.registry_output, audit_path=args.audit_output, registry=registry, audit=audit)
        print(json.dumps({"status": "batch_approval_applied", "source_count": len(registry["sources"]), "registry": str(registry_path), "audit": str(audit_path)}, ensure_ascii=False))
        return 0
    except PotentialScopeBatchApprovalError as error:
        raise SystemExit(f"PotentialScope batch approval failed safely: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
