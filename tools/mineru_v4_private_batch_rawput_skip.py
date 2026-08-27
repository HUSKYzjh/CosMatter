#!/usr/bin/env python3
"""Submit a selected slice of an authorised MinerU v4 PDF batch.

This wrapper is used after a one-file transport probe so a proven file is not
uploaded twice.  It retains the private manifest and raw signed PUT safeguards
from ``mineru_v4_private_batch_rawput.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SOURCE = Path(__file__).with_name("mineru_v4_private_batch_rawput.py")
SPEC = importlib.util.spec_from_file_location("cosmatter_mineru_v4_rawput", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Cannot load private MinerU raw-PUT implementation")
rawput = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rawput
SPEC.loader.exec_module(rawput)
batch = rawput.batch


def take_skip_option() -> int:
    arguments = sys.argv[1:]
    try:
        position = arguments.index("--skip-files")
    except ValueError:
        return 0
    if position + 1 >= len(arguments):
        raise SystemExit("--skip-files requires a non-negative integer")
    try:
        skip = int(arguments[position + 1])
    except ValueError as error:
        raise SystemExit("--skip-files requires a non-negative integer") from error
    if skip < 0:
        raise SystemExit("--skip-files requires a non-negative integer")
    del arguments[position : position + 2]
    sys.argv = [sys.argv[0], *arguments]
    return skip


SKIP = take_skip_option()
ORIGINAL_GET_PDFS = batch.get_pdfs


def get_remaining_pdfs(roots: list[Path], max_files: int) -> list[tuple[Path, Path]]:
    # Request the whole local inventory from the verified implementation, then
    # select a deterministic non-overlapping range.  The base implementation
    # still verifies actual PDFs and the provider's 200-file cap.
    all_files = ORIGINAL_GET_PDFS(roots, 0)
    selected = all_files[SKIP:]
    if max_files:
        selected = selected[:max_files]
    if not selected:
        raise ValueError("no PDFs remain after --skip-files")
    if len(selected) > 200:
        raise ValueError("MinerU v4 accepts at most 200 files per batch")
    return selected


batch.get_pdfs = get_remaining_pdfs

if __name__ == "__main__":
    raise SystemExit(batch.main())
