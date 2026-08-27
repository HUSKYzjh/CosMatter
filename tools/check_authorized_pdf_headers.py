#!/usr/bin/env python3
"""Record only format metadata for an explicitly authorised local PDF corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = [path.resolve() for path in args.input]
    files = [(root, pdf) for root in roots for pdf in sorted(root.rglob("*.pdf")) if pdf.is_file()]
    invalid: list[dict[str, object]] = []
    largest = 0
    for root, pdf in files:
        size = pdf.stat().st_size
        largest = max(largest, size)
        with pdf.open("rb") as stream:
            header = stream.read(16)
        if not header.startswith(b"%PDF-"):
            invalid.append({"source_root": root.name, "source_relative_path": pdf.relative_to(root).as_posix(), "byte_count": size, "header_hex": header.hex()})
    result = {"total_files": len(files), "pdf_signature_valid": len(files) - len(invalid), "invalid_or_misnamed": invalid, "largest_bytes": largest}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total_files": result["total_files"], "pdf_signature_valid": result["pdf_signature_valid"], "invalid_or_misnamed": len(invalid), "largest_bytes": largest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
