"""Pure helpers for minimising failures in isolated DSH bundle combinations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import combinations
from typing import Any


class DshCombinationLabError(ValueError):
    pass


def normalize_package_selection(available: Iterable[str], requested: Iterable[str]) -> tuple[str, ...]:
    available_tuple = tuple(available)
    selected = tuple(requested)
    if not available_tuple or len(set(available_tuple)) != len(available_tuple) or any(not isinstance(item, str) or not item for item in available_tuple):
        raise DshCombinationLabError("available bundle list is invalid")
    if not selected or len(set(selected)) != len(selected) or any(item not in available_tuple for item in selected):
        raise DshCombinationLabError("selected bundle list is invalid")
    return tuple(item for item in available_tuple if item in set(selected))


def all_pairs(available: Iterable[str]) -> tuple[tuple[str, str], ...]:
    names = tuple(available)
    if len(names) < 2 or len(set(names)) != len(names):
        raise DshCombinationLabError("pairwise bundle list is invalid")
    return tuple(combinations(names, 2))


def minimise_failing_combination(selected: Iterable[str], probe: Callable[[tuple[str, ...]], bool]) -> tuple[str, ...] | None:
    """Return a 1-minimal failing subset using only a supplied isolated probe.

    ``probe`` returns true for a healthy combination.  The algorithm never
    calls DSH itself; callers decide how each clean-profile probe is run.
    """
    current = tuple(selected)
    if not current or probe(current):
        return None
    granularity = 2
    while len(current) >= 2:
        chunks = _chunks(current, granularity)
        reduced = False
        for chunk in chunks:
            candidate = tuple(item for item in current if item not in set(chunk))
            if candidate and not probe(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)
    return current


def compact_report(*, selected: Iterable[str], healthy: bool, minimal_failure: Iterable[str] | None, probe_count: int) -> dict[str, Any]:
    bundles = tuple(selected)
    minimal = tuple(minimal_failure or ())
    if not bundles or not isinstance(healthy, bool) or not isinstance(probe_count, int) or probe_count < 1:
        raise DshCombinationLabError("combination report fields are invalid")
    if healthy and minimal:
        raise DshCombinationLabError("healthy combination cannot have a minimal failure")
    return {
        "schema_version": "1.0",
        "trust_status": "isolated_dsh_combination_diagnostic_not_provider_execution_or_scientific_evidence",
        "selected_bundle_count": len(bundles),
        "selected_bundles": list(bundles),
        "healthy": healthy,
        "probe_count": probe_count,
        "minimal_failure_bundles": list(minimal),
    }


def _chunks(items: tuple[str, ...], count: int) -> tuple[tuple[str, ...], ...]:
    size = max(1, (len(items) + count - 1) // count)
    return tuple(items[index : index + size] for index in range(0, len(items), size))
