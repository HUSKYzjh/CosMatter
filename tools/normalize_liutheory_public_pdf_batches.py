#!/usr/bin/env python3
"""Make source-derived Liu Theory Lab PDF batch identifiers globally unique."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must not already exist")
    args.output.mkdir(parents=True)
    seen: set[str] = set()
    for source in sorted(args.input.glob("batch-*.allowlist.json")):
        value = json.loads(source.read_text(encoding="utf-8"))
        documents = value.get("documents") if isinstance(value, dict) else None
        if not isinstance(documents, list):
            raise ValueError(f"invalid batch: {source.name}")
        for row in documents:
            if not isinstance(row, dict) or not isinstance(row.get("source_url"), str):
                raise ValueError(f"invalid document in {source.name}")
            digest = hashlib.sha256(row["source_url"].encode("utf-8")).hexdigest()[:12]
            row["document_id"] = f"liutheory-{digest}"
            if row["document_id"] in seen:
                raise ValueError("duplicate public source URL")
            seen.add(row["document_id"])
        (args.output / source.name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batches": len(list(args.output.glob("batch-*.allowlist.json"))), "documents": len(seen)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
