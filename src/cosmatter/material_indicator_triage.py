"""Deterministically shortlist private MinerU segments for indicator review.

The result is a private, unreviewed navigation aid.  It deliberately retains
exact source excerpts so a reviewer can inspect values and conditions, but it
is neither a Source Map nor evidence and must stay outside the repository.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


SHORTLIST_SCHEMA_VERSION = "cosmatter.private-material-indicator-shortlist/v1"
SHORTLIST_TRUST_STATUS = "private_unreviewed_local_indicator_shortlist_not_source_map_or_evidence"
POOL_TRUST_STATUS = "private_unreviewed_mineru_markdown_candidate_pool_not_source_map"
_MAX_SEGMENTS_PER_DOCUMENT = 2
_MAX_TOTAL_SEGMENTS = 12


class MaterialIndicatorTriageError(ValueError):
    """Raised when an indicator shortlist input or result is unsafe or invalid."""


_INDICATOR_TERMS: dict[str, tuple[str, ...]] = {
    "spontaneous_polarization_ps": (
        "spontaneous polarization", "remanent polarization", "polarisation", "polarization",
        "hysteresis loop", "p-e loop", "p(e)",
    ),
    "hysteresis_saturation": (
        "saturat", "unsaturat", "hysteresis loop", "coercive field", "cycling field",
    ),
    "epitaxial_strain": (
        "epitaxial strain", "compressive strain", "tensile strain", "lattice mismatch", "misfit strain",
    ),
    "tetragonality_c_over_a": (
        "c/a", "tetragonality", "tetragonal-like", "t-like", "t phase",
    ),
    "space_group": (
        "space group", "r3c", "pbnm", "pnma", "rhombohedral", "orthorhombic", "monoclinic",
        "tetragonal", "m_a", "m_c", "ma phase", "mc phase",
    ),
    "ferroelectric_transition_temperature": (
        "ferroelectric transition", "curie temperature", "curie point", "alpha-beta transition",
        "beta-to-alpha", "beta to alpha", "ferroelectric to paraelectric", "ferroelectric – paraelectric",
        "paraelectric beta", "paraelectric β",
    ),
    "insulator_metal_transition_temperature": (
        "metal-insulator", "insulator-metal", "metallic", "semiconducting", "gamma phase",
    ),
    "domain_wall_conductivity": (
        "domain-wall conduction", "domain wall conduction", "domain-wall conductivity",
        "domain wall conductivity", "conductive wall", "conducting wall", "conductive dws",
        "fraction of conductive", "fractions of dws", "dws exhibiting current", "c-afm",
    ),
    "conductive_domain_wall_fraction": (
        "conductive wall fraction", "conductive domain wall fraction", "fraction of conductive",
        "fractions of dws", "dws exhibiting current", "fraction of the analysed dws",
    ),
    "resistance_switching_ratio": (
        "switching ratio", "on/off", "on-off", "resistance ratio", "orders of magnitude",
    ),
    "saturation_magnetization_ms": (
        "saturation magnetization", "saturation magnetisation", "saturation moment",
        "m_s", "m s", "ms=", "ms =",
    ),
    "remanent_magnetization_mr": (
        "remanent magnetization", "remanent magnetisation", "remanence",
        "m_r", "m r", "mr=", "mr =",
    ),
    "magnetic_coercive_field_hc": (
        "magnetic coercive field", "coercive magnetic field", "coercivity",
        "h_c", "h c", "hc=", "hc =",
    ),
    "exchange_bias_field": (
        "exchange bias", "exchange-bias", "bias field", "h_eb", "heb",
    ),
    "magnetic_moment_per_fe": (
        "magnetic moment per fe", "moment per fe", "bohr magneton per fe",
        "u_b/fe", "ub/fe", "mu_b/fe",
    ),
    "cycloid_period": (
        "cycloid period", "cycloidal period", "cycloid wavelength", "spin cycloid",
        "magnetic cycloid", "modulation period",
    ),
    "direct_band_gap": (
        "direct band gap", "direct bandgap", "direct optical gap", "direct transition",
    ),
    "indirect_band_gap": (
        "indirect band gap", "indirect bandgap", "indirect optical gap", "indirect transition",
    ),
    "absorption_coefficient": (
        "absorption coefficient", "absorption coefficients", "linear absorption",
        "alpha=", "alpha =", "optical absorption",
    ),
    "refractive_index": (
        "refractive index", "index of refraction", "optical index", "n=", "n =",
    ),
    "open_circuit_voltage": (
        "open-circuit voltage", "open circuit voltage", "v_oc", "v oc", "voc=", "voc =",
    ),
    "short_circuit_current_density": (
        "short-circuit current density", "short circuit current density", "short-circuit current",
        "short circuit current", "zero-bias photocurrent density", "photocurrent density",
        "j_sc", "j sc", "jsc=", "jsc =", "i_sc", "i sc", "isc=", "isc =",
    ),
    "photoresponsivity": (
        "photoresponsivity", "photo-responsivity", "photodetector responsivity", "responsivity",
    ),
    "deposition_rate": (
        "deposition rate", "growth rate", "film growth rate", "deposited per minute",
        "deposited per second",
    ),
    "replicate_batch_count": (
        "independent batches", "separate batches", "different batches", "three batches",
        "batches were", "batch-to-batch", "batch to batch", "total samples", "total specimens",
    ),
}

_NUMERIC_RE = re.compile(
    r"(?<![A-Za-z])(?:[<>~≈]?\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
    r"(?:\s*(?:±|\+/-|to|[-–—])\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+))?"
    r"(?:\s*[×x]\s*10\s*\^?\s*[+-]?\d+|\s*[eE][+-]?\d+)?)"
)
_UNIT_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    r"(?:μ|µ|u)c\s*/\s*cm(?:\^?2|²)|kv\s*/\s*cm|mv\s*/\s*cm|v\s*/\s*(?:cm|m)|"
    r"°\s*c|deg\s*c|kelvin|k|%|nm|μm|µm|angstrom|å|pa|na|μa|µa|ma|"
    r"(?:n|u|m)?a\s*/\s*cm(?:\^?2|²)|s\s*/\s*cm|ev|mev|hz|khz|mhz|pm\s*/\s*v|"
    r"emu\s*/\s*cm(?:\^?3|³)|(?:u|mu)[_ ]?b\s*/\s*fe|oe|mt|"
    r"(?:cm|m)\s*(?:\^?\s*-\s*1|⁻¹)|(?:n|u|m)?a\s*/\s*w|pc\s*/\s*n|"
    r"(?:nm|angstrom|å)\s*/\s*(?:s|min)|(?:m|u)?v|batches?|specimens?|samples?"
    r")(?![A-Za-z])",
    re.IGNORECASE,
)
_CONDITION_TERMS = (
    "temperature", "room temperature", "liquid nitrogen", "frequency", "field", "bias",
    "thickness", "substrate", "electrode", "orientation", "oriented", "direction", "along",
    "single crystal", "thin film", "ceramic", "polycrystalline", "powder", "anneal", "quench",
    "cooling", "heating", "oxygen", "atmosphere", "cycle", "sample",
)
_METHOD_TERMS = (
    "measured", "measurement", "determined", "observed", "x-ray", "diffraction", "neutron",
    "raman", "conductive afm", "c-afm", "pfm", "microscopy", "spectroscopy", "hysteresis",
    "current-voltage", "i-v", "reciprocal space map",
)
_BOUNDARY_TERMS = (
    "however", "although", "cannot", "could not", "limited", "limitation", "decomposition",
    "unsaturated", "degradation", "uncertainty", "not observed", "no evidence", "depends on",
    "rather than", "in contrast", "only", "approximately",
)
_RESULT_TERMS = (
    "we measured", "we measure", "we find", "we found", "we extract", "we infer",
    "our measurement", "our results", "we observe", "we observed", "we demonstrate",
    "we demonstrated", "we have demonstrated", "this study demonstrates", "investigation demonstrates",
    "demonstrates that",
)
_BACKGROUND_TERMS = (
    "theoretical studies", "calculations predict", "recently", "previously reported",
    "according to the authors", "in thin films", "reference ",
)
_CITED_COMPARISON_TERMS = (
    "according to the authors", "these authors reported", "who found", "as reported by",
)
_REFERENCE_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,4}\s*)?(?:references|bibliography)\b|"
    r"(?:^|\n)\s*\[?\d{1,3}\]?\s+[A-Z][A-Za-z-]+(?:\s+et\s+al\.)?.{0,100}\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


def _normalized_scientific_text(value: str) -> str:
    """Normalize common MinerU TeX spacing only for deterministic matching."""
    text = value.casefold().replace("μ", "u").replace("µ", "u")
    text = re.sub(r"</?(?:sup|sub)>", "", text)
    text = text.replace("\\mu", "u").replace("\\textdegree", " deg ").replace("\\circ", " deg ")
    text = re.sub(r"\\(?:mathrm|mathbf|textup|mathfrak|mathsf|tt)\s*", " ", text)
    text = text.replace("\\", " ").replace("$", " ").replace("{", " ").replace("}", " ").replace("~", " ")
    # MinerU often renders 820 as ``8 2 0`` and uC/cm2 as
    # ``u C . c m ^ - 2``. This form is used for matching only; the original
    # quote and its hash remain unchanged.
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    text = re.sub(r"u\s*c\s*[.·]\s*c\s*m\s*\^?\s*-\s*2", "uc/cm2", text)
    text = re.sub(r"u\s*c\s*/\s*c\s*m\s*\^?\s*2", "uc/cm2", text)
    text = re.sub(r"([num]?)\s*a\s*/\s*c\s*m\s*\^?\s*2", r"\1a/cm2", text)
    text = re.sub(r"([num]?)\s*a\s*/\s*w", r"\1a/w", text)
    text = re.sub(r"m\s*w\s*/\s*c\s*m\s*\^?\s*2", "mw/cm2", text)
    text = re.sub(r"e\s*m\s*u\s*/\s*c\s*m\s*\^?\s*3", "emu/cm3", text)
    text = re.sub(r"\bdeg\s*(?:o\s*)?c\b", "degc", text)
    return re.sub(r"\s+", " ", text).strip()


def _indicator_value_hits(text: str, matched: list[str]) -> int:
    hits = 0
    if "spontaneous_polarization_ps" in matched and re.search(r"uc\s*/\s*cm(?:2|\^2)", text):
        hits += 1
    if "hysteresis_saturation" in matched and re.search(r"(?:uc\s*/\s*cm(?:2|\^2)|kv\s*/\s*cm|saturat)", text):
        hits += 1
    if "epitaxial_strain" in matched and "%" in text:
        hits += 1
    if "tetragonality_c_over_a" in matched and re.search(
        r"\bc\s*/\s*a\s*(?:ratio\s*)?(?:(?:was|is|of|changes?\s+from|from)\s*)?"
        r"(?:e|≈|=)?\s*1\.\d+(?:\s*(?:to|[-–—])\s*1\.\d+)?\b", text,
    ):
        hits += 1
    if any(item in matched for item in ("ferroelectric_transition_temperature", "insulator_metal_transition_temperature")) and re.search(r"(?:\bdegc\b|°\s*c|\b\d{3,4}\s*k\b)", text):
        hits += 1
    if "domain_wall_conductivity" in matched and re.search(
        r"(?:s\s*/\s*cm|a\s*/\s*cm2|\b(?:pa|na|ua|ma)\b|conductive\s+(?:fraction|walls?)|"
        r"fractions?\s+of\s+(?:the\s+)?dws?.{0,80}(?:current|conductive))", text,
    ):
        hits += 1
    if "conductive_domain_wall_fraction" in matched and "%" in text:
        hits += 1
    if "resistance_switching_ratio" in matched and re.search(r"(?:orders? of magnitude|on\s*[/−-]\s*off|switching ratio)", text):
        hits += 1
    if "space_group" in matched and re.search(r"\b(?:r3c|pbnm|pnma|p4mm|cc)\b", text):
        hits += 1
    if any(item in matched for item in ("saturation_magnetization_ms", "remanent_magnetization_mr")) and re.search(
        r"(?:emu\s*/\s*cm(?:3|\^3)|(?:u|mu)[_ ]?b\s*/\s*fe)", text,
    ):
        hits += 1
    if any(item in matched for item in ("magnetic_coercive_field_hc", "exchange_bias_field")) and re.search(
        r"(?:\boe\b|\bmt\b|\btesla\b)", text,
    ):
        hits += 1
    if "magnetic_moment_per_fe" in matched and re.search(r"(?:u|mu)[_ ]?b\s*/\s*fe|bohr magneton.{0,20}fe", text):
        hits += 1
    if "cycloid_period" in matched and re.search(r"(?:nm|angstrom|å)\b", text):
        hits += 1
    if any(item in matched for item in ("direct_band_gap", "indirect_band_gap")) and re.search(r"\b(?:m?ev)\b", text):
        hits += 1
    if "absorption_coefficient" in matched and re.search(r"(?:cm|m)\s*(?:\^?\s*-\s*1|⁻¹)", text):
        hits += 1
    if "open_circuit_voltage" in matched and re.search(r"\b(?:m?v)\b", text):
        hits += 1
    if "short_circuit_current_density" in matched and re.search(r"(?:n|u|m)?a\s*/\s*cm(?:2|\^2)", text):
        hits += 1
    if "photoresponsivity" in matched and re.search(r"(?:n|u|m)?a\s*/\s*w", text):
        hits += 1
    if "deposition_rate" in matched and re.search(r"(?:nm|angstrom|å)\s*/\s*(?:s|min)", text):
        hits += 1
    if "replicate_batch_count" in matched and re.search(
        r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(?:independent\s+)?(?:batches?|specimens?|samples?)\b",
        text,
    ):
        hits += 1
    return hits


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _score_segment(segment: dict[str, str], focus_indicator_ids: list[str]) -> dict[str, Any] | None:
    quote = segment["quote"]
    text = _normalized_scientific_text(quote)
    matched = [
        indicator_id
        for indicator_id in focus_indicator_ids
        if _contains_any(text, _INDICATOR_TERMS.get(indicator_id, (indicator_id.replace("_", " "),)))
    ]
    has_number = _NUMERIC_RE.search(text) is not None
    has_unit = _UNIT_RE.search(text) is not None
    has_range = (
        re.search(r"[+-]?\d+(?:\.\d+)?\s*(?:to|[-–—])\s*[+-]?\d+(?:\.\d+)?", text) is not None
        or re.search(r"\bc\s*/\s*a.{0,40}\bfrom\s+1\.\d+.{0,40}\bto\s+1\.\d+", text) is not None
    )
    condition_hits = sum(term in text for term in _CONDITION_TERMS)
    method_hits = sum(term in text for term in _METHOD_TERMS)
    boundary_hits = sum(term in text for term in _BOUNDARY_TERMS)
    result_hits = sum(term in text for term in _RESULT_TERMS)
    background_hits = sum(term in text for term in _BACKGROUND_TERMS)
    cited_comparison = any(term in text for term in _CITED_COMPARISON_TERMS)
    indicator_value_hits = _indicator_value_hits(text, matched)
    off_target_property = re.search(r"\b(?:band\s*gap|electronic density of states|density of states)\b", text) is not None and not any(
        indicator_id in focus_indicator_ids
        for indicator_id in ("band_gap", "electronic_structure")
    )
    off_target_energy = re.search(r"\b\d+(?:\.\d+)?\s*(?:m?ev)\b", text) is not None and not any(
        indicator_id in focus_indicator_ids
        for indicator_id in ("band_gap", "activation_energy", "energy_barrier")
    )
    reference_like = segment["locator"].startswith("markdown_reference_line:") or _REFERENCE_RE.search(quote) is not None

    # A generic number alone is too weak.  Keep an excerpt only when it names a
    # target indicator, or when a measured value/unit is tied to method/context.
    if not matched and not (has_number and (has_unit or condition_hits or method_hits)):
        return None

    score = 8 * len(matched)
    score += 5 if has_number else 0
    score += 4 if has_unit else 0
    score += 8 if has_range else 0
    score += 6 if matched and has_number and has_unit else 0
    score += min(condition_hits, 4) * 2
    score += min(method_hits, 3) * 2
    score += min(boundary_hits, 2)
    score += min(result_hits, 2) * 6
    score += indicator_value_hits * 14
    score -= min(background_hits, 2) * 10
    score -= 12 if cited_comparison else 0
    score -= 12 if off_target_property else 0
    score -= 12 if off_target_energy else 0
    if segment["kind"] == "figure_caption" and matched and has_number:
        score += 4
    if reference_like:
        score -= 18
    if score <= 0:
        return None

    candidate_roles: list[str] = []
    reason_codes: list[str] = []
    if has_number or has_unit:
        candidate_roles.append("reported_value_candidate")
        reason_codes.append("numeric_or_unit_expression")
    if has_range:
        reason_codes.append("numeric_range_expression")
    if condition_hits:
        candidate_roles.append("measurement_condition_candidate")
        reason_codes.append("measurement_context_term")
    if method_hits:
        candidate_roles.append("measurement_method_candidate")
        reason_codes.append("measurement_method_term")
    if boundary_hits:
        candidate_roles.append("boundary_or_limitation_candidate")
        reason_codes.append("boundary_term")
    if result_hits:
        reason_codes.append("primary_result_language")
    if background_hits:
        reason_codes.append("background_or_cited_comparison_penalty")
    if cited_comparison:
        reason_codes.append("explicit_cited_comparison_penalty")
    if off_target_property:
        reason_codes.append("off_target_property_penalty")
    if off_target_energy:
        reason_codes.append("off_target_energy_value_penalty")
    if indicator_value_hits:
        reason_codes.append("indicator_compatible_value_or_unit")
    if matched:
        reason_codes.append("focus_indicator_term")
    if reference_like:
        reason_codes.append("reference_like_penalty")

    return {
        "segment_id": segment["segment_id"],
        "locator": segment["locator"],
        "kind": segment["kind"],
        "quote": quote,
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        "matched_indicator_ids": matched,
        "candidate_roles": candidate_roles,
        "reason_codes": reason_codes,
        "score": score,
    }


def _validate_pool(pool: object, *, document_id: str, expected_markdown_hash: str) -> dict[str, Any]:
    if not isinstance(pool, dict):
        raise MaterialIndicatorTriageError("private review pool must be an object")
    if pool.get("trust_status") != POOL_TRUST_STATUS or pool.get("document_id") != document_id:
        raise MaterialIndicatorTriageError("private review pool identity or trust status does not match")
    if pool.get("source_markdown_sha256") != expected_markdown_hash:
        raise MaterialIndicatorTriageError("private review pool Markdown hash does not match its index")
    segments = pool.get("candidate_segments")
    if not isinstance(segments, list) or not segments:
        raise MaterialIndicatorTriageError("private review pool has no candidate segments")
    seen: set[str] = set()
    for item in segments:
        if not isinstance(item, dict) or set(item) != {"segment_id", "locator", "kind", "quote"}:
            raise MaterialIndicatorTriageError("private review pool segment fields are invalid")
        if not all(isinstance(item[key], str) and item[key].strip() for key in item):
            raise MaterialIndicatorTriageError("private review pool segment values are invalid")
        if item["segment_id"] in seen or len(item["quote"]) > 500:
            raise MaterialIndicatorTriageError("private review pool segment boundary is invalid")
        seen.add(item["segment_id"])
    return pool


def _source_scopes(matrix: object) -> dict[str, dict[str, Any]]:
    if not isinstance(matrix, dict) or matrix.get("schema_version") != "cosmatter.material-source-candidate-matrix/v1":
        raise MaterialIndicatorTriageError("material source matrix schema is unsupported")
    result: dict[str, dict[str, Any]] = {}
    for question in matrix.get("questions", []):
        if not isinstance(question, dict):
            raise MaterialIndicatorTriageError("material source matrix question is invalid")
        focus_ids = question.get("focus_indicator_ids")
        if not isinstance(focus_ids, list) or not focus_ids or not all(isinstance(value, str) and value for value in focus_ids):
            raise MaterialIndicatorTriageError("material source matrix focus indicators are invalid")
        for source in question.get("source_candidates", []):
            if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
                raise MaterialIndicatorTriageError("material source candidate is invalid")
            if source["source_id"] in result:
                raise MaterialIndicatorTriageError("material source candidate IDs must be unique")
            result[source["source_id"]] = {
                "question_id": question.get("question_id"),
                "focus_indicator_ids": focus_ids,
                "source_role": source.get("role"),
                "access_status": source.get("access_status"),
            }
    return result


def build_private_indicator_shortlist(
    *,
    matrix: object,
    review_index: object,
    pools_by_document: dict[str, object],
    max_total_segments: int = _MAX_TOTAL_SEGMENTS,
    max_segments_per_document: int = _MAX_SEGMENTS_PER_DOCUMENT,
) -> dict[str, Any]:
    """Build a bounded, hash-bound shortlist without making factual claims."""
    if not 1 <= max_total_segments <= _MAX_TOTAL_SEGMENTS:
        raise MaterialIndicatorTriageError("shortlist total limit must be between 1 and 12")
    if not 1 <= max_segments_per_document <= _MAX_SEGMENTS_PER_DOCUMENT:
        raise MaterialIndicatorTriageError("per-document shortlist limit must be between 1 and 2")
    if not isinstance(review_index, dict) or review_index.get("trust_status") != "private_unreviewed_mineru_manifest_review_index_not_evidence":
        raise MaterialIndicatorTriageError("private review index identity or trust status is invalid")
    entries = review_index.get("entries")
    if not isinstance(entries, list) or not entries:
        raise MaterialIndicatorTriageError("private review index has no entries")
    scopes = _source_scopes(matrix)

    per_document: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise MaterialIndicatorTriageError("private review index entry is invalid")
        document_id = entry.get("document_id")
        markdown_hash = entry.get("markdown_sha256")
        if not isinstance(document_id, str) or not isinstance(markdown_hash, str):
            raise MaterialIndicatorTriageError("private review index entry identity is invalid")
        scope = scopes.get(document_id)
        if scope is None or scope["access_status"] != "private_mineru_review_pool_ready":
            raise MaterialIndicatorTriageError("private review document is not a ready source-matrix candidate")
        if document_id not in pools_by_document:
            raise MaterialIndicatorTriageError("private review pool is missing for an indexed document")
        pool = _validate_pool(pools_by_document[document_id], document_id=document_id, expected_markdown_hash=markdown_hash)
        ranked = []
        for order, segment in enumerate(pool["candidate_segments"]):
            scored = _score_segment(segment, scope["focus_indicator_ids"])
            if scored is not None:
                ranked.append((scored, order))
        ranked.sort(key=lambda item: (-item[0]["score"], item[1], item[0]["segment_id"]))
        selected = [item[0] for item in ranked[:max_segments_per_document]]
        if selected:
            per_document.append(
                {
                    "document_id": document_id,
                    "source_markdown_sha256": pool["source_markdown_sha256"],
                    "question_id": scope["question_id"],
                    "source_role": scope["source_role"],
                    "focus_indicator_ids": list(scope["focus_indicator_ids"]),
                    "segments": selected,
                }
            )

    # Preserve document coverage first.  First-ranked segments from all sources
    # precede second-ranked segments when a caller requests a smaller total cap.
    chosen: dict[str, list[dict[str, Any]]] = {item["document_id"]: [] for item in per_document}
    remaining = max_total_segments
    for rank in range(max_segments_per_document):
        for item in per_document:
            if remaining == 0:
                break
            if rank < len(item["segments"]):
                chosen[item["document_id"]].append(item["segments"][rank])
                remaining -= 1
        if remaining == 0:
            break
    documents = [
        {**{key: value for key, value in item.items() if key != "segments"}, "segments": chosen[item["document_id"]]}
        for item in per_document
        if chosen[item["document_id"]]
    ]
    segment_count = sum(len(item["segments"]) for item in documents)
    if not segment_count:
        raise MaterialIndicatorTriageError("no indicator-relevant private segments met the deterministic threshold")
    return {
        "schema_version": SHORTLIST_SCHEMA_VERSION,
        "mission_id": review_index.get("mission_id"),
        "material_scope": matrix.get("material_scope"),
        "catalog_id": matrix.get("catalog_id"),
        "trust_status": SHORTLIST_TRUST_STATUS,
        "selection_method": "deterministic_indicator_numeric_condition_ranking_v1",
        "document_count": len(documents),
        "segment_count": segment_count,
        "limits": {
            "max_total_segments": max_total_segments,
            "max_segments_per_document": max_segments_per_document,
            "max_quote_chars": 500,
        },
        "documents": documents,
        "review_boundary": (
            "These exact excerpts are private navigation candidates only. Validate each value, unit, qualifier, "
            "table or figure context, and source location before creating a Source Map or material fact."
        ),
    }
