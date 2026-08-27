import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


def evaluation(route_shift: float) -> dict:
    return {
        "schema_version": "1.1", "mission_id": "mission_90", "corpus_id": "bfo_90",
        "trust_status": "metrics_from_human_reviewed_gold_standard",
        "identity_resolution_policy": "exact_document_id_or_normalized_doi_to_frozen_manifest",
        "search_index": 0, "k": 10, "raw_retrieved_count": 12, "retrieved_count": 10,
        "doi_resolved_candidate_count": 2, "duplicate_alias_count": 1,
        "gold_relevant_count": 8, "gold_partially_relevant_count": 4,
        "precision_at_k": 0.4 + route_shift, "recall_at_k": 0.5 + route_shift,
        "ndcg_at_k": 0.52 + route_shift,
    }


class RetrievalRouteComparisonCliTests(unittest.TestCase):
    def test_writes_aggregate_route_comparison_without_labels_or_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comparison_input = root / "routes.json"
            comparison_input.write_text(json.dumps({
                "baseline_route_id": "keyword",
                "routes": [
                    {"route_id": "keyword", "evaluation": evaluation(0.0)},
                    {"route_id": "hybrid", "evaluation": evaluation(0.1)},
                ],
            }), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["compare-human-retrieval-routes", "--run-id", "bfo_90", "--input", str(comparison_input)])
            result_output = output.getvalue()
            saved_path = root / "runs" / "bfo_90" / "human_retrieval_route_comparison.json"
            saved = saved_path.read_text(encoding="utf-8") if saved_path.is_file() else ""
        self.assertEqual(status, 0, result_output)
        self.assertIn("ndcg_at_k_delta", saved)
        self.assertNotIn("retrieval_relevance", saved)
        self.assertNotIn("query", saved)


if __name__ == "__main__":
    unittest.main()
