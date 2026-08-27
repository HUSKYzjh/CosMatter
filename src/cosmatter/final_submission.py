"""Build a sealed preliminary-submission package from reviewed public artifacts.

The package contains source, an already compiled LaTeX report, citation audit,
and a human-reviewed external-resource disclosure.  It deliberately never
copies a full-text cache, private Markdown, a run directory wholesale, or any
credential-bearing configuration.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .submission_bundle import _allowlisted_paths
from .submission_readiness import submission_readiness


SCHEMA_VERSION = "1.0"
_REPORT_FILES = (
    "main.tex", "references.bib", "main.pdf", "citation_audit.json",
    "latex_report_manifest.json",
)
_REAL_EVALUATION_FILES = (
    "real_corpus_evaluation_run_record.json",
    "frozen_corpus_readiness.json",
    "human_annotation_coverage.json",
    "bibliographic_source_coverage.json",
    "evaluation_failure_case_log.json",
    "evaluation_api_cost_latency.json",
    "human_retrieval_evaluation.json",
    "human_material_fact_evaluation.json",
    "human_evidence_quality_evaluation.json",
    "human_gap_evaluation.json",
)


class FinalSubmissionError(ValueError):
    """Raised when the reviewed submission boundary has not been met."""


def build_final_submission_package(*, repository_root: Path, run_dir: Path, output_path: Path) -> dict[str, Any]:
    repository_root, run_dir, output_path = repository_root.resolve(), run_dir.resolve(), output_path.resolve()
    if output_path.suffix.lower() != ".zip" or repository_root not in output_path.parents:
        raise FinalSubmissionError("final submission package must be a ZIP inside the repository root")
    readiness = submission_readiness(repository_root=repository_root, run_dir=run_dir)
    if not readiness["ready"]:
        failed = sorted(name for name, passed in readiness["checks"].items() if not passed)
        raise FinalSubmissionError("final submission package is blocked by: " + ", ".join(failed))
    report_dir = run_dir / "latex_submission"
    disclosure = run_dir / "external_resource_disclosure.json"
    source_paths = tuple(_allowlisted_paths(repository_root))
    evaluation_record = _completed_real_evaluation_record(run_dir, readiness)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written: list[str] = []
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_paths:
            arcname = f"source/{path.relative_to(repository_root).as_posix()}"
            _write(archive, path, arcname, digest, written)
        for name in _REPORT_FILES:
            _write(archive, report_dir / name, f"report/{name}", digest, written)
        _write(archive, disclosure, "report/external_resource_disclosure.json", digest, written)
        if evaluation_record is not None:
            for name in _REAL_EVALUATION_FILES:
                _write(archive, run_dir / name, f"evaluation/{name}", digest, written)
        readiness_bytes = json.dumps(readiness, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        archive.writestr("report/submission_readiness.json", readiness_bytes)
        digest.update(b"report/submission_readiness.json\0" + hashlib.sha256(readiness_bytes).digest())
        written.append("report/submission_readiness.json")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "trust_status": "review_gated_submission_package_not_scientific_or_reference_authenticity_assessment",
            "run_id": run_dir.name,
            "source_file_count": len(source_paths),
            "report_files": list(_REPORT_FILES),
            "external_resource_disclosure": "report/external_resource_disclosure.json",
            "real_evaluation_artifacts": [f"evaluation/{name}" for name in _REAL_EVALUATION_FILES] if evaluation_record is not None else [],
            "excluded_categories": ["runs except allowed report files", "full text", "private Markdown", "credentials", "provider payloads"],
            "package_content_sha256": digest.hexdigest(),
            "human_checks_remaining": readiness["required_human_checks"],
        }
        archive.writestr("SUBMISSION_PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        **manifest,
        "package_path": str(output_path),
        "package_sha256": _file_sha256(output_path),
    }


def _completed_real_evaluation_record(run_dir: Path, readiness: dict[str, Any]) -> dict[str, Any] | None:
    """Return a reviewed record only when it declares a consistent completed evaluation."""
    record_path = run_dir / "real_corpus_evaluation_run_record.json"
    if not record_path.is_file():
        return None
    if readiness.get("checks", {}).get("run_real_evaluation_record_consistent") is not True:
        raise FinalSubmissionError("final submission package cannot include an inconsistent real evaluation record")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FinalSubmissionError("real evaluation record cannot be read") from error
    if not isinstance(record, dict) or record.get("submission_truth_check") != "completed":
        return None
    return record


def _write(archive: zipfile.ZipFile, path: Path, arcname: str, digest: hashlib._Hash, written: list[str]) -> None:
    if not path.is_file():
        raise FinalSubmissionError(f"required final submission file is missing: {arcname}")
    data = path.read_bytes()
    archive.writestr(arcname, data)
    digest.update(arcname.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    written.append(arcname)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
