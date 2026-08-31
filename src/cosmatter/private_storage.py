"""Private, local-only storage for user-authorized PDF parser output.

Nothing in this module returns filesystem paths to browser-facing code.  The
run directory receives only hash-bound task metadata; original PDFs, ZIPs and
full Markdown stay in this separate cache.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .config import data_root


class PrivateStorageError(ValueError):
    pass


def private_root() -> Path:
    """Return local case data outside the code tree and run subdirectories."""
    root = data_root() / "private"
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_document_id(run_id: str, file_name: str, content: bytes) -> str:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
        raise PrivateStorageError("run_id is invalid")
    if not isinstance(file_name, str) or not file_name.lower().endswith(".pdf"):
        raise PrivateStorageError("file_name must be a PDF")
    return "pdf_" + hashlib.sha256((run_id + "\0" + file_name).encode("utf-8") + content).hexdigest()[:24]


def pdf_path(document_id: str) -> Path:
    return _document_dir(document_id) / "input.pdf"


def markdown_path(document_id: str) -> Path:
    return _document_dir(document_id) / "full.md"


def write_pdf(document_id: str, content: bytes) -> tuple[Path, str]:
    if not content.startswith(b"%PDF-") or len(content) > 200 * 1024 * 1024:
        raise PrivateStorageError("content must be a PDF of at most 200 MB")
    path = pdf_path(document_id)
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def write_markdown(document_id: str, content: bytes) -> tuple[Path, str]:
    if not content or len(content) > 80 * 1024 * 1024:
        raise PrivateStorageError("MinerU Markdown size is invalid")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PrivateStorageError("MinerU Markdown must be UTF-8") from error
    path = markdown_path(document_id)
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def read_markdown(document_id: str) -> bytes:
    path = markdown_path(document_id)
    if not path.is_file():
        raise PrivateStorageError("private Markdown is not available")
    return path.read_bytes()


def _document_dir(document_id: str) -> Path:
    if not isinstance(document_id, str) or not re.fullmatch(r"pdf_[a-f0-9]{24}", document_id):
        raise PrivateStorageError("document_id is invalid")
    path = private_root() / document_id
    path.mkdir(parents=True, exist_ok=True)
    return path
