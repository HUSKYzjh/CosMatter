"""Conservative deterministic validation for reviewer-proposed unit conversions.

The validator never guesses a unit from prose or a fact name.  It only checks a
reviewer's numeric pair when both units belong to one explicit supported family.
Unknown units and textual quantities remain reviewable instead of being silently
converted or rejected.
"""

from __future__ import annotations

import math
import unicodedata


class UnitNormalizationError(ValueError):
    """Raised when a known-unit normalized pair is dimensionally inconsistent."""


# Every alias is normalized first with NFKC, case folding, no whitespace, no
# caret notation, and micro-sign -> Greek-mu -> ASCII ``u``.  This lets us accept
# common PDF/OCR forms without treating arbitrary prose as a physical unit.
_ALIASES = {
    # Length
    "m": "m", "cm": "cm", "mm": "mm", "um": "um", "nm": "nm", "pm": "pm",
    "angstrom": "angstrom", "\u00e5": "angstrom", "a0": "bohr", "bohr": "bohr",
    # Temperature
    "k": "k", "kelvin": "k", "degc": "degc", "\u00b0c": "degc", "celsius": "degc",
    # Pressure
    "pa": "pa", "kpa": "kpa", "mpa": "mpa", "gpa": "gpa", "bar": "bar",
    # Energy
    "ev": "ev", "mev": "mev", "kev": "kev", "j": "j",
    # Ferroelectric polarization
    "c/m2": "c/m2", "uc/cm2": "uc/cm2",
    # Electric field
    "v/m": "v/m", "kv/cm": "kv/cm", "mv/cm": "mv/cm",
    # Strain
    "%": "percent", "percent": "percent", "fraction": "fraction",
    # Magnetization (SI and a common cgs reporting unit)
    "a/m": "a/m", "ka/m": "ka/m", "ma/m": "ma/m", "emu/cm3": "emu/cm3",
    # Frequency and density are common reported experimental conditions.
    "hz": "hz", "khz": "khz", "mhz": "mhz", "ghz": "ghz",
    "kg/m3": "kg/m3", "g/cm3": "g/cm3",
}

_FACTORS = {
    "length": {
        "m": 1.0, "cm": 1e-2, "mm": 1e-3, "um": 1e-6, "nm": 1e-9,
        "pm": 1e-12, "angstrom": 1e-10, "bohr": 5.29177210903e-11,
    },
    "pressure": {"pa": 1.0, "kpa": 1e3, "mpa": 1e6, "gpa": 1e9, "bar": 1e5},
    "energy": {"ev": 1.0, "mev": 1e-3, "kev": 1e3, "j": 6.241509074e18},
    "polarization": {"c/m2": 1.0, "uc/cm2": 1e-2},
    "electric_field": {"v/m": 1.0, "kv/cm": 1e5, "mv/cm": 1e8},
    "strain": {"fraction": 1.0, "percent": 1e-2},
    "magnetization": {"a/m": 1.0, "ka/m": 1e3, "ma/m": 1e6, "emu/cm3": 1e3},
    "frequency": {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9},
    "density": {"kg/m3": 1.0, "g/cm3": 1e3},
}


def validate_reported_normalization(
    value: object, unit: object, normalized_value: object, normalized_unit: object,
) -> None:
    """Reject only provably inconsistent known-unit numeric normalizations.

    A conversion check is intentionally *not* an entity extractor or ontology:
    it cannot infer whether an unlabelled ``1.5`` is thickness, strain, or a
    composition.  The reviewer must supply both source and target unit.
    """
    if not _is_number(value) or not _is_number(normalized_value):
        return
    source_unit = _canonical_unit(unit)
    target_unit = _canonical_unit(normalized_unit)
    if source_unit is None or target_unit is None:
        return
    family = _family(source_unit)
    if family is None or family != _family(target_unit):
        raise UnitNormalizationError("reported and normalized units are not in the same supported dimension")
    expected = _convert(float(value), source_unit, target_unit, family)
    if not math.isclose(expected, float(normalized_value), rel_tol=1e-7, abs_tol=1e-10):
        raise UnitNormalizationError("normalized value does not match the reported numeric value and units")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _canonical_unit(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(normalized.split()).replace("^", "").replace("?", "-")
    normalized = normalized.replace("\u03bc", "u").replace("\u00b5", "u")
    return _ALIASES.get(normalized)


def _family(unit: str) -> str | None:
    if unit in {"k", "degc"}:
        return "temperature"
    for family, factors in _FACTORS.items():
        if unit in factors:
            return family
    return None


def _convert(value: float, source_unit: str, target_unit: str, family: str) -> float:
    if family == "temperature":
        in_kelvin = value if source_unit == "k" else value + 273.15
        return in_kelvin if target_unit == "k" else in_kelvin - 273.15
    factors = _FACTORS[family]
    return value * factors[source_unit] / factors[target_unit]
