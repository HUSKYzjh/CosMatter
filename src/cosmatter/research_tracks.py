"""Shared constants for approved research-query and reading-route tracks."""

from __future__ import annotations


RESEARCH_TRACKS = ("exact_material", "mechanism_analogue", "algorithm")
DEFAULT_TRACK_CANDIDATE_MINIMUMS = {
    "exact_material": 4,
    "mechanism_analogue": 3,
    "algorithm": 4,
}
MAX_READING_ROUTE_ITEMS = 12
