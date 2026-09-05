"""Run-level boundary for delegated technical trials.

The marker is intentionally checked by presence only.  A delegated trial must
never regain scientific or publication authority because its marker was
malformed, partially written, or left behind after older workflow code ran.
Formal human review belongs in a fresh run without this marker.
"""

from __future__ import annotations

from pathlib import Path


DELEGATED_TEST_REVIEW_MARKER = "test_only_delegated_review.json"


def has_delegated_test_review_boundary(run_dir: Path) -> bool:
    """Return true whenever the run is permanently marked as test-only."""
    return (run_dir / DELEGATED_TEST_REVIEW_MARKER).exists()
