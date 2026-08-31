import copy
import json
import unittest
from pathlib import Path

from cosmatter.market_snapshot_review import MarketSnapshotReviewError, snapshot_diff, verify_market_snapshot_review


class MarketSnapshotReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "configs"
        self.baseline = json.loads((root / "dsh_market_snapshot.baseline.json").read_text(encoding="utf-8"))
        self.current = json.loads((root / "dsh_market_snapshot.json").read_text(encoding="utf-8"))
        self.review = json.loads((root / "dsh_market_snapshot_review.json").read_text(encoding="utf-8"))

    def test_checked_in_review_binds_the_current_snapshot(self) -> None:
        result = verify_market_snapshot_review(baseline=self.baseline, current=self.current, review=self.review)
        self.assertEqual(result["added_count"], 0)
        self.assertEqual(result["removed_count"], 0)
        self.assertEqual(result["changed_count"], 0)
        self.assertNotIn("https://", json.dumps(result))

    def test_unreviewed_candidate_change_is_rejected_and_diff_redacts_urls(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["candidates"].append(
            {"candidate_id": "new-plugin", "category": "test", "source_url": "https://github.com/example/new-plugin", "observed_ref": "unversioned_public_discovery", "status": "untrusted_discovery_only"}
        )
        diff = snapshot_diff(self.baseline, changed)
        self.assertEqual(diff["added_count"], 1)
        self.assertNotIn("https://", json.dumps(diff))
        with self.assertRaises(MarketSnapshotReviewError):
            verify_market_snapshot_review(baseline=self.baseline, current=changed, review=self.review)
