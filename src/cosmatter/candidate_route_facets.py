"""Deterministic metadata facets for bounded research-route balancing.

These signals are navigation heuristics, not relevance judgments.  They use
only mission text, approved query provenance, and candidate titles; no model,
provider call, abstract, full text, or property prediction is involved.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .models import MissionBrief


RESEARCH_TRACKS = ("exact_material", "mechanism_analogue", "algorithm")
ROUTE_ELIGIBILITIES = ("primary_allowed", "counterevidence_only")
TRACK_MINIMUMS = {"exact_material": 4, "mechanism_analogue": 3, "algorithm": 4}
COUNTEREVIDENCE_MINIMUM = 1
FACET_SIGNALS = {
    "exact_material_title",
    "material_family_title",
    "configuration_search_method",
    "molecular_dynamics_method",
    "property_surrogate_method",
    "mission_forbids_property_surrogate",
    "approved_counterevidence_query",
}

_ALGORITHM_PATTERNS = (
    r"\b(?:global|combinatorial|configuration|configurational)\s+(?:search|optim(?:ization|isation))\b",
    r"\b(?:genetic|evolutionary|memetic)\s+algorithm\b",
    r"\b(?:simulated annealing|basin hopping|particle swarm|cross entropy method)\b",
    r"\b(?:black[ -]?box|derivative[ -]?free)\s+optim(?:ization|isation)\b",
    r"\b(?:monte carlo|metropolis|wang[ -]?landau|parallel tempering|replica exchange)\b",
    r"\b(?:bayesian optim(?:ization|isation)|active learning)\b",
    r"(?:构型|组分|全局|组合)(?:空间)?(?:搜索|优化)",
    r"遗传算法|进化算法|模拟退火|蒙特卡洛|并行回火|副本交换|贝叶斯优化|主动学习",
)
_MOLECULAR_DYNAMICS_PATTERNS = (r"\bmolecular dynamics\b", r"\bmd simulations?\b", r"分子动力学")
_SURROGATE_PATTERNS = (
    r"\bsurrogate (?:model|predictor|prediction)\b",
    r"\bproperty prediction (?:model|surrogate)\b",
    r"\bpredictive model for (?:dielectric|piezoelectric|material propert)",
    r"\bgaussian process (?:model|regression|surrogate)\b",
    r"\bneural network (?:property )?predictor\b",
    r"\bbayesian optim(?:ization|isation)\b",
    r"性质预测(?:代理|模型)|代理模型|高斯过程(?:回归|代理)|贝叶斯优化",
)
_FAMILY_PATTERNS = (
    r"\bperovskites?\b", r"\bferroelectric\b", r"\bpiezoelectric\b", r"\bdielectric\b",
    r"\btitanates?\b", r"\bsolid solutions?\b", r"\bcation (?:order|ordering|disorder)\b",
    r"\bshort[ -]?range order\b", r"钙钛矿|铁电|压电|介电|固溶体|阳离子(?:有序|无序)|短程有序",
)
_FORBIDDEN_SURROGATE_PATTERNS = (
    r"\b(?:no|without|absent) (?:a )?(?:property )?(?:prediction )?surrogate\b",
    r"\bproperty (?:data|values?) (?:are|is) only (?:available|obtained) (?:from|by) (?:molecular dynamics|md)\b",
    r"不存在性质预测(?:的)?代理模型|无性质预测代理|无代理模型|只能由分子动力学(?:模拟)?获得",
)


def classify_candidate_route(
    mission: MissionBrief,
    candidate: dict[str, Any],
    *,
    approved_counterevidence_query: bool,
) -> dict[str, Any]:
    """Return allowlisted route facets without asserting scientific relevance."""
    title = candidate.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("candidate title is required for route faceting")
    title_text = _normalized_text(title)
    mission_text = _normalized_text(f"{mission.question} {mission.material} {mission.property_name} {mission.scope}")
    exact = _exact_material_title(mission_text, title_text)
    algorithm = _matches_any(title_text, _ALGORITHM_PATTERNS)
    family = _matches_any(title_text, _FAMILY_PATTERNS)
    md = _matches_any(title_text, _MOLECULAR_DYNAMICS_PATTERNS)
    surrogate = _matches_any(title_text, _SURROGATE_PATTERNS)
    forbids_surrogate = _matches_any(mission_text, _FORBIDDEN_SURROGATE_PATTERNS)

    if exact:
        research_track = "exact_material"
    elif algorithm:
        research_track = "algorithm"
    else:
        research_track = "mechanism_analogue"
    signals: list[str] = []
    if exact:
        signals.append("exact_material_title")
    if family:
        signals.append("material_family_title")
    if algorithm:
        signals.append("configuration_search_method")
    if md:
        signals.append("molecular_dynamics_method")
    if surrogate:
        signals.append("property_surrogate_method")
    if surrogate and forbids_surrogate:
        signals.append("mission_forbids_property_surrogate")
    if approved_counterevidence_query:
        signals.append("approved_counterevidence_query")
    return {
        "research_track": research_track,
        "route_eligibility": "counterevidence_only" if approved_counterevidence_query or surrogate and forbids_surrogate else "primary_allowed",
        "facet_signals": signals,
    }


def _exact_material_title(mission_text: str, title_text: str) -> bool:
    mission_compact = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", mission_text)
    title_compact = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", title_text)
    if _is_pst_target(mission_compact):
        return (
            bool(re.search(r"pb[a-z0-9]{0,24}sr[a-z0-9]{0,24}tio3", title_compact))
            or "leadstrontiumtitanate" in title_compact
            or bool(re.search(r"\bpst\b", title_text)) and _matches_any(title_text, (r"\bperovskite\b", r"\btitanate\b", r"\bferroelectric\b"))
        )
    if "bifeo3" in mission_compact or "bismuthferrite" in mission_compact:
        return "bifeo3" in title_compact or "bismuthferrite" in title_compact
    target_formulas = _formula_tokens(mission_text)
    return bool(target_formulas) and any(formula in title_compact for formula in target_formulas)


def _is_pst_target(compact: str) -> bool:
    return "leadstrontiumtitanate" in compact or "pbst" in compact and "tio3" in compact or all(token in compact for token in ("pb", "sr", "tio3"))


def _formula_tokens(value: str) -> tuple[str, ...]:
    raw = unicodedata.normalize("NFKC", value).replace("₀", "0").replace("₁", "1").replace("₂", "2").replace("₃", "3")
    formulas = re.findall(r"\b(?:[A-Z][a-z]?\d*){2,}\b", raw)
    return tuple(dict.fromkeys(re.sub(r"[^a-z0-9]", "", item.casefold()) for item in formulas))


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value, flags=re.IGNORECASE) is not None for pattern in patterns)


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("−", "-").replace("–", "-")
