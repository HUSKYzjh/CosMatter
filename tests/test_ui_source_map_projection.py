import unittest

from cosmatter.ui_export import _paper_source_map_projection


class UiSourceMapProjectionTests(unittest.TestCase):
    def test_projects_only_a_few_bounded_reviewed_segments(self) -> None:
        source_map = {
            "document_id": "doc_1",
            "segments": [
                {"segment_id": "p1", "locator": "p. 1", "kind": "paragraph", "quote": "a" * 400, "quote_sha256": "ignored"},
                {"segment_id": "p2", "locator": "p. 2", "kind": "table", "quote": "b" * 400, "quote_sha256": "ignored"},
                {"segment_id": "p3", "locator": "p. 3", "kind": "formula", "quote": "c" * 400, "quote_sha256": "ignored"},
            ],
        }
        projected = _paper_source_map_projection(source_map)
        self.assertEqual(projected["document_id"], "doc_1")
        self.assertEqual(len(projected["segments"]), 2)
        self.assertNotIn("quote_sha256", projected["segments"][0])

    def test_missing_source_map_stays_absent(self) -> None:
        self.assertIsNone(_paper_source_map_projection(None))
