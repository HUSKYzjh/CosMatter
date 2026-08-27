#!/usr/bin/env python3
"""Submit only structurally valid PDFs from an explicitly authorised corpus.

The separate integrity record retains invalid or misnamed ``.pdf`` files for
human replacement; this program never renames, alters, or uploads them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SOURCE = Path(__file__).with_name("mineru_v4_private_batch_rawput_skip.py")
SPEC = importlib.util.spec_from_file_location("cosmatter_mineru_v4_rawput_skip", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Cannot load private MinerU batch implementation")
skip_wrapper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = skip_wrapper
SPEC.loader.exec_module(skip_wrapper)
batch = skip_wrapper.batch


def get_valid_remaining_pdfs(roots: list[Path], max_files: int) -> list[tuple[Path, Path]]:
    all_files = skip_wrapper.ORIGINAL_GET_PDFS(roots, 0)
    valid: list[tuple[Path, Path]] = []
    for root, pdf in all_files:
        with pdf.open("rb") as stream:
            if stream.read(5).startswith(b"%PDF-"):
                valid.append((root, pdf))
    selected = valid[skip_wrapper.SKIP:]
    if max_files:
        selected = selected[:max_files]
    if not selected:
        raise ValueError("no valid PDFs remain after --skip-files")
    if len(selected) > 200:
        raise ValueError("MinerU v4 accepts at most 200 files per batch")
    return selected


batch.get_pdfs = get_valid_remaining_pdfs

if __name__ == "__main__":
    raise SystemExit(batch.main())
