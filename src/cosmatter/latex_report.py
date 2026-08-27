"""Submission-safe LaTeX rendering for reviewed CosMatter evidence reports.

The competition requires a compiled PDF together with ``.tex`` and ``.bib``
sources.  This module deliberately renders only review-gated, short evidence
records.  It never reads a PDF, private Markdown, provider payload, API token,
or local path.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .gap_analysis import ResearchGapCandidate
from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


LATEX_REPORT_SCHEMA_VERSION = "1.1"


class LatexReportError(ValueError):
    """Raised when a submission report cannot prove its citation boundary."""


@dataclass(frozen=True)
class LatexReportExport:
    output_dir: Path
    tex_path: Path
    bib_path: Path
    manifest_path: Path
    citation_audit_path: Path


def compile_latex_report(export: LatexReportExport) -> Path:
    """Compile an already audited source package without shell interpolation."""
    xelatex, bibtex = shutil.which("xelatex"), shutil.which("bibtex")
    if xelatex is None or bibtex is None:
        raise LatexReportError("XeLaTeX and BibTeX are required to compile the submission PDF")
    commands = (
        (xelatex, "-interaction=nonstopmode", "-halt-on-error", export.tex_path.name),
        (bibtex, export.tex_path.stem),
        (xelatex, "-interaction=nonstopmode", "-halt-on-error", export.tex_path.name),
        (xelatex, "-interaction=nonstopmode", "-halt-on-error", export.tex_path.name),
    )
    for command in commands:
        completed = subprocess.run(
            command, cwd=export.output_dir, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if completed.returncode:
            raise LatexReportError(f"LaTeX compilation failed for {command[0]}: {completed.stdout[-1200:]}")
    pdf_path = export.output_dir / "main.pdf"
    if not pdf_path.is_file() or pdf_path.stat().st_size < 1024:
        raise LatexReportError("LaTeX compilation did not produce a usable PDF")
    return pdf_path

def export_latex_report(
    *,
    output_dir: Path,
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    document_metadata: tuple[dict[str, Any], ...],
    research_gap_candidates: tuple[ResearchGapCandidate, ...] = (),
) -> LatexReportExport:
    """Render a minimal LaTeX source package from accepted evidence only."""
    accepted = _accepted_cards(mission, cards, decisions)
    metadata = _metadata_index(document_metadata)
    used_documents = {card.provenance.document_id for card in accepted}
    missing = sorted(document_id for document_id in used_documents if document_id not in metadata)
    if missing:
        raise LatexReportError(
            "accepted EvidenceCards lack candidate bibliographic metadata: " + ", ".join(missing)
        )
    _validate_gap_candidates(mission, accepted, research_gap_candidates)
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path, bib_path = output_dir / "main.tex", output_dir / "references.bib"
    bibliography = {document_id: metadata[document_id] for document_id in used_documents}
    cite_keys = {document_id: _cite_key(document_id) for document_id in used_documents}
    source_labels = {document_id: str(metadata[document_id]["source"]).strip() for document_id in used_documents}
    disclosed_bibliographic_sources = sorted(set(source_labels.values()))
    tex_path.write_text(
        _render_tex(mission, accepted, research_gap_candidates, cite_keys, source_labels), encoding="utf-8"
    )
    bib_path.write_text(_render_bibliography(bibliography, cite_keys), encoding="utf-8")
    audit = audit_latex_citations(
        tex=tex_path.read_text(encoding="utf-8"),
        bibliography=bib_path.read_text(encoding="utf-8"),
        accepted_cards=accepted,
        cite_keys=cite_keys,
    )
    audit_path = output_dir / "citation_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": LATEX_REPORT_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": "review_gated_latex_source_not_scientific_validity_assessment",
        "tex_file": tex_path.name,
        "bib_file": bib_path.name,
        "citation_audit_file": audit_path.name,
        "accepted_evidence_count": len(accepted),
        "bibliography_entry_count": len(bibliography),
        "research_gap_candidate_count": len(research_gap_candidates),
        "accepted_evidence_source_disclosure_coverage": 1.0,
        "bibliographic_source_count": len(disclosed_bibliographic_sources),
        "bibliographic_sources": disclosed_bibliographic_sources,
        "every_accepted_evidence_row_discloses_bibliographic_source": True,
        "no_private_fulltext_or_provider_payload": True,
    }
    manifest_path = output_dir / "latex_report_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return LatexReportExport(output_dir, tex_path, bib_path, manifest_path, audit_path)


def audit_latex_citations(
    *,
    tex: str,
    bibliography: str,
    accepted_cards: tuple[EvidenceCard, ...],
    cite_keys: dict[str, str],
) -> dict[str, Any]:
    """Check every rendered evidence source is cited and bibliography-backed."""
    cited = {
        key.strip()
        for raw in re.findall(r"\\(?:cite|parencite|textcite)\{([^}]+)\}", tex)
        for key in raw.split(",")
        if key.strip()
    }
    entries = set(re.findall(r"@\w+\{([^,\s]+),", bibliography, flags=re.IGNORECASE))
    expected = set(cite_keys.values())
    if cited != expected:
        raise LatexReportError("LaTeX citation keys do not exactly match accepted evidence sources")
    if entries != expected:
        raise LatexReportError("BibTeX entries do not exactly match cited evidence sources")
    missing_cards = [
        card.evidence_id
        for card in accepted_cards
        if cite_keys[card.provenance.document_id] not in cited
    ]
    if missing_cards:
        raise LatexReportError("accepted EvidenceCards are missing citations: " + ", ".join(missing_cards))
    return {
        "schema_version": LATEX_REPORT_SCHEMA_VERSION,
        "trust_status": "citation_structure_audit_not_reference_authenticity_assessment",
        "accepted_evidence_count": len(accepted_cards),
        "citation_key_count": len(cited),
        "bibliography_entry_count": len(entries),
        "accepted_evidence_citation_coverage": 1.0,
        "citation_bibliography_bijection": True,
        "human_reference_authenticity_check_required": True,
    }


def _accepted_cards(
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
) -> tuple[EvidenceCard, ...]:
    accepted_ids = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission.mission_id and decision.status is ReviewStatus.ACCEPTED
    }
    accepted = tuple(card for card in cards if card.evidence_id in accepted_ids)
    if not accepted:
        raise LatexReportError("LaTeX report export requires at least one accepted EvidenceCard")
    if len({card.evidence_id for card in accepted}) != len(accepted):
        raise LatexReportError("accepted EvidenceCards have duplicate identifiers")
    return accepted


def _metadata_index(records: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        document_id, title, source = record.get("document_id"), record.get("title"), record.get("source")
        if not isinstance(document_id, str) or not document_id or not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(source, str) or not source.strip():
            raise LatexReportError(
                "candidate bibliographic metadata must disclose a non-empty source for every document"
            )
        if document_id in index:
            raise LatexReportError("candidate bibliographic metadata contains duplicate document IDs")
        index[document_id] = record
    return index


def _validate_gap_candidates(
    mission: MissionBrief,
    accepted: tuple[EvidenceCard, ...],
    candidates: tuple[ResearchGapCandidate, ...],
) -> None:
    accepted_ids = {card.evidence_id for card in accepted}
    for candidate in candidates:
        if (
            candidate.material != mission.material
            or candidate.property_name != mission.property_name
            or candidate.review_status != "candidate_requires_human_review"
            or not set(candidate.evidence_ids).issubset(accepted_ids)
        ):
            raise LatexReportError("Research Gap candidate is outside the accepted evidence boundary")


def _cite_key(document_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9:_-]+", "_", document_id).strip("_") or "document"
    digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:8]
    return f"cm_{normalized[:48]}_{digest}"


def _tex_escape(value: object) -> str:
    text = str(value)
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(character, character) for character in text)


def _render_tex(
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    candidates: tuple[ResearchGapCandidate, ...],
    cite_keys: dict[str, str],
    source_labels: dict[str, str],
) -> str:
    lines = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[UTF8]{ctex}",
        r"\usepackage[margin=2.2cm]{geometry}",
        r"\usepackage{booktabs,longtable,hyperref}",
        r"\title{CosMatter 文献调研报告：" + _tex_escape(mission.material) + "}",
        r"\author{CosMatter evidence workflow}",
        r"\date{}",
        r"\begin{document}", r"\maketitle",
        r"\section{任务边界}",
        "研究问题：" + _tex_escape(mission.question) + r"\\",
        "研究对象与性质：" + _tex_escape(mission.material) + " / " + _tex_escape(mission.property_name) + r"\\",
        "比较范围：" + _tex_escape(mission.scope) + ".",
        r"\section{证据登记表}",
        "本报告仅呈现已通过人工审核、具有来源定位的 EvidenceCard。每一行的“书目数据库/来源”来自对应候选文献元数据，并同时写入 BibTeX；它与原文定位字段分别记录，不能互相替代。其内容是可回溯的文献记录，不构成自动生成的科学结论。",
        r"\begin{longtable}{p{0.12\linewidth}p{0.13\linewidth}p{0.16\linewidth}p{0.17\linewidth}p{0.28\linewidth}}",
        r"\toprule Evidence ID & 书目数据库/来源 & 文献定位 & 立场与条件 & 已审核主张 \\ \midrule \endhead",
    ]
    for card in cards:
        conditions = "; ".join(f"{key}={value}" for key, value in sorted(card.conditions.items())) or "未记录"
        source = f"{_tex_escape(card.provenance.document_id)}; {_tex_escape(card.provenance.locator)}; \\cite{{{cite_keys[card.provenance.document_id]}}}"
        lines.append(
            f"{_tex_escape(card.evidence_id)} & {_tex_escape(source_labels[card.provenance.document_id])} & {source} & {_tex_escape(card.stance.value)}; {_tex_escape(conditions)} & {_tex_escape(card.claim)} \\\\"
        )
    lines += [r"\bottomrule", r"\end{longtable}", r"\section{Research Gap 候选（待人工复核）}"]
    if not candidates:
        lines.append("当前没有满足证据门禁的 Research Gap 候选。")
    else:
        card_by_id = {card.evidence_id: card for card in cards}
        for candidate in candidates:
            keys = sorted({cite_keys[card_by_id[evidence_id].provenance.document_id] for evidence_id in candidate.evidence_ids})
            lines += [
                r"\subsection{" + _tex_escape(candidate.gap_id) + "}",
                "问题：" + _tex_escape(candidate.problem_description) + r"\\",
                "证据缺失或冲突：" + _tex_escape("; ".join(candidate.conflict_or_missing_evidence)) + r"\\",
                "可证伪假设：" + _tex_escape(candidate.falsifiable_hypothesis) + r"\\",
                "建议验证：" + _tex_escape("; ".join(candidate.suggested_validation)) + r"\\",
                "支撑文献：" + r"\cite{" + ",".join(keys) + "}。",
            ]
    lines += [
        r"\section{审计边界}",
        "文献来源、定位、条件字段与人工审核状态必须在使用前逐项核对。引用结构审计只能验证条目映射，不替代对原文与书目信息真实性的人工核验。",
        r"\bibliographystyle{plain}", r"\bibliography{references}", r"\end{document}", "",
    ]
    return "\n".join(lines)


def _render_bibliography(records: dict[str, dict[str, Any]], cite_keys: dict[str, str]) -> str:
    entries: list[str] = []
    for document_id in sorted(records):
        record = records[document_id]
        title = _bib_escape(str(record["title"]))
        source = _bib_escape(str(record.get("source", "unspecified metadata source")))
        fields = [f"  title = {{{title}}}", f"  howpublished = {{Bibliographic database/source: {source}}}"]
        year = record.get("publication_year")
        if isinstance(year, int):
            fields.append(f"  year = {{{year}}}")
        doi = record.get("doi")
        if isinstance(doi, str) and doi.strip():
            fields.append(f"  doi = {{{_bib_escape(doi)}}}")
        fields.append(f"  note = {{CosMatter document ID: {_bib_tex_escape(document_id)}}}")
        entries.append("@misc{" + cite_keys[document_id] + ",\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(entries) + "\n"



def _bib_tex_escape(value: str) -> str:
    return _tex_escape(value)

def _bib_escape(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")
