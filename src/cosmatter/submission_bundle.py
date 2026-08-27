"""Allowlisted preliminary-submission source bundle builder."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Iterable


BUNDLE_SCHEMA_VERSION = "1.0"
_ROOT_FILES = ("README.md", "REPRODUCIBILITY.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "CITATION.cff", "pyproject.toml", "requirements.lock", ".gitignore")
_ROOT_DIRS = ("src", "tests", "configs", "docs", "examples", ".github")
_FRONTEND_FILES = ("package.json", "package-lock.json", "tsconfig.json", "vite.config.ts", "index.html", "README.md")
_FRONTEND_DIRS = ("src", "public")
_DISALLOWED_PARTS = {".env", ".venv", "runs", ".private", "node_modules", "dist", "__pycache__", ".git"}
_DISALLOWED_SUFFIXES = {".pdf", ".docx", ".zip", ".tar", ".gz", ".parquet", ".sqlite", ".db"}


class SubmissionBundleError(ValueError):
    """Raised when an allowlisted submission bundle cannot be produced."""


def build_source_bundle(*, repository_root: Path, output_path: Path) -> dict[str, object]:
    """Zip only reproducible source artifacts; do not inspect secrets or runs."""
    repository_root = repository_root.resolve()
    output_path = output_path.resolve()
    if output_path.suffix.lower() != ".zip":
        raise SubmissionBundleError("submission bundle output must end in .zip")
    if repository_root not in output_path.parents:
        raise SubmissionBundleError("submission bundle output must remain inside the repository root")
    paths = tuple(_allowlisted_paths(repository_root))
    if not paths:
        raise SubmissionBundleError("no allowlisted source files are available")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root_name = repository_root.name
    digest = hashlib.sha256()
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            relative = path.relative_to(repository_root)
            data = path.read_bytes()
            digest.update(relative.as_posix().encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
            archive.writestr(f"{root_name}/{relative.as_posix()}", data)
        manifest = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "trust_status": "allowlisted_source_bundle_no_runs_secrets_or_third_party_fulltext",
            "source_file_count": len(paths),
            "source_tree_sha256": digest.hexdigest(),
            "included_paths": [path.relative_to(repository_root).as_posix() for path in paths],
            "excluded_categories": [".env", "runs", "private full text", "node_modules", "frontend/dist", "build archives", "editable chroma-key visual sources"],
        }
        archive.writestr(f"{root_name}/SUBMISSION_BUNDLE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**manifest, "bundle_path": str(output_path), "bundle_sha256": _file_sha256(output_path)}


def _allowlisted_paths(root: Path) -> Iterable[Path]:
    candidates: list[Path] = []
    for name in _ROOT_FILES:
        path = root / name
        if path.is_file():
            candidates.append(path)
    for name in _ROOT_DIRS:
        directory = root / name
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    frontend = root / "frontend"
    for name in _FRONTEND_FILES:
        path = frontend / name
        if path.is_file():
            candidates.append(path)
    for name in _FRONTEND_DIRS:
        directory = frontend / name
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    result = []
    for path in candidates:
        relative = path.relative_to(root)
        if _safe_source_path(relative):
            result.append(path)
    return tuple(sorted(set(result), key=lambda item: item.relative_to(root).as_posix()))


def _safe_source_path(relative: Path) -> bool:
    parts = set(relative.parts)
    if parts.intersection(_DISALLOWED_PARTS) or relative.name.startswith(".env"):
        return False
    if relative.suffix.lower() in _DISALLOWED_SUFFIXES:
        return False
    if relative.parts[:3] == ("frontend", "public", "background-sources"):
        return False
    return True


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
