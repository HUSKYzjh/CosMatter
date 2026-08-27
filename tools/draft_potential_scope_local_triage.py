"""Create quote-free, offline PotentialScope routing drafts and a blank review sheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_local_triage import (
    PotentialScopeLocalTriageError,
    build_local_batch_review_template,
    build_local_keyword_triage,
    write_once,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local-only PotentialScope routing drafts.")
    parser.add_argument("--review-index", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    try:
        index = json.loads(args.review_index.read_text(encoding="utf-8"))
        mission_id = index["mission_id"]
        entries = index["entries"]
        if not isinstance(mission_id, str) or not isinstance(entries, list) or not entries:
            raise PotentialScopeLocalTriageError("private review index is invalid")
        if "runs" in {part.casefold() for part in args.output_directory.parts}:
            raise PotentialScopeLocalTriageError("output directory must remain outside CosMatter/runs")
        drafts = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("pool_filename"), str):
                raise PotentialScopeLocalTriageError("private review index entry is invalid")
            pool_path = args.review_index.parent / entry["pool_filename"]
            pool = json.loads(pool_path.read_text(encoding="utf-8"))
            draft = build_local_keyword_triage(pool)
            write_once(args.output_directory / f"{draft['document_id']}.local-triage.json", draft)
            drafts.append(draft)
        template = build_local_batch_review_template(mission_id=mission_id, drafts=drafts)
        write_once(args.output_directory / "local-keyword-triage.batch-review.template.json", template)
    except (OSError, json.JSONDecodeError, KeyError, PotentialScopeLocalTriageError) as error:
        raise SystemExit(f"local PotentialScope triage was not created: {error}") from error
    print(json.dumps({"status": "local_private_triage_prepared", "documents": len(drafts), "output_directory": str(args.output_directory), "trust_status": "untrusted_local_keyword_private_potential_scope_source_triage_not_evidence", "execution_permitted": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
