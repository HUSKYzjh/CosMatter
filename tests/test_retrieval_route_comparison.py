import unittest

from cosmatter.retrieval_route_comparison import RetrievalRouteComparisonError, compare_human_retrieval_routes


def evaluation(*, precision: float, recall: float, ndcg: float, k: int = 10) -> dict:
    return {
        "schema_version": "1.1", "mission_id": "mission_90", "corpus_id": "bfo_90",
        "trust_status": "metrics_from_human_reviewed_gold_standard",
        "identity_resolution_policy": "exact_document_id_or_normalized_doi_to_frozen_manifest",
        "search_index": 0, "k": k, "raw_retrieved_count": 12, "retrieved_count": 10,
        "doi_resolved_candidate_count": 4, "duplicate_alias_count": 2,
        "gold_relevant_count": 8, "gold_partially_relevant_count": 5,
        "precision_at_k": precision, "recall_at_k": recall, "ndcg_at_k": ndcg,
    }


class RetrievalRouteComparisonTests(unittest.TestCase):
    def test_compares_only_same_boundary_aggregate_metrics(self) -> None:
        comparison = compare_human_retrieval_routes(
            routes=[
                {"route_id": "keyword", "evaluation": evaluation(precision=0.4, recall=0.5, ndcg=0.48)},
                {"route_id": "hybrid_multi_agent", "evaluation": evaluation(precision=0.6, recall=0.75, ndcg=0.72)},
            ],
            baseline_route_id="keyword",
        )
        candidate = comparison["route_metrics"][1]
        self.assertEqual(comparison["baseline_route_id"], "keyword")
        self.assertEqual(candidate["relative_to_baseline"]["ndcg_at_k_delta"], 0.24)
        self.assertNotIn("query", str(comparison))

    def test_rejects_mixed_k_or_corpus_boundaries(self) -> None:
        with self.assertRaises(RetrievalRouteComparisonError):
            compare_human_retrieval_routes(
                routes=[
                    {"route_id": "keyword", "evaluation": evaluation(precision=0.4, recall=0.5, ndcg=0.48)},
                    {"route_id": "semantic", "evaluation": evaluation(precision=0.5, recall=0.6, ndcg=0.58, k=20)},
                ],
                baseline_route_id="keyword",
            )


if __name__ == "__main__":
    unittest.main()
