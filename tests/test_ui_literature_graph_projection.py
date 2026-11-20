import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.models import MissionBrief
from cosmatter.ui_export import _literature_graph_projection, _retrieval_candidate_projection


class UiLiteratureGraphProjectionTests(unittest.TestCase):
    def test_candidate_projection_excludes_query_scores_and_raw_fields(self) -> None:
        payload = {
            "candidates": [
                {
                    "document_id": "paper_1",
                    "title": "Bounded paper title",
                    "source": "Sciverse",
                    "publication_year": 2024,
                    "is_content_accessible": True,
                    "query": "never send this query",
                    "score": 0.998,
                    "abstract": "never send this abstract",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retrieval_candidates.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            candidates = _retrieval_candidate_projection(path)
        self.assertEqual(candidates[0]["title"], "Bounded paper title")
        serialised = json.dumps(candidates)
        self.assertNotIn("never send", serialised)
        self.assertNotIn("score", serialised)

    def test_candidate_projection_keeps_bounded_reading_guide_items_in_the_graph_window(self) -> None:
        payload = {
            "candidates": [
                {
                    "document_id": f"paper_{index}",
                    "title": f"Bounded paper title {index}",
                    "source": "fixture",
                    "publication_year": 2024,
                    "is_content_accessible": False,
                }
                for index in range(60)
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retrieval_candidates.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            candidates = _retrieval_candidate_projection(path, ("paper_59", "paper_58"))

        self.assertEqual(len(candidates), 48)
        self.assertEqual([item["document_id"] for item in candidates[:2]], ["paper_59", "paper_58"])
        self.assertNotIn("_source_order", json.dumps(candidates))

    def test_fact_ledgers_preserve_existing_paper_metadata_and_review_boundaries(self) -> None:
        mission = MissionBrief("question", "BiFeO3", "phase", "films", mission_id="mission_graph")
        candidates = [{"document_id": "candidate", "title": "Reported dielectric response", "source": "Sciverse",
                       "publication_year": 2025, "is_content_accessible": True}]
        evidence = [{"evidence_id": "e1", "claim": "Reviewed claim", "provenance": {"document_id": "accepted", "source": "fixture", "access_policy": "oa"}}]
        relations = {"source": {"document_id": "references"}, "edges": [{"target_openalex_id": "https://openalex.org/W2", "edge_type": "citation_reference"}]}
        structure = {"document_id": "structured", "entities": [], "relations": [], "trust_status": "human_reviewed_paper_structure_not_scientific_evidence"}
        args = (mission, evidence, candidates, relations, None, structure)
        baseline = _literature_graph_projection(*args)
        fact_trust = "human_reviewed_structured_material_facts_not_scientific_conclusion"
        ledgers = tuple({"document_id": doc, "trust_status": fact_trust} for doc in ("candidate", "accepted", "structured", "references", "fact-only"))
        updated = _literature_graph_projection(*args, material_fact_ledgers=ledgers)
        self.assertEqual(baseline["edges"], updated["edges"])
        nodes = {node["node_id"]: node for node in updated["nodes"]}
        for original in baseline["nodes"]:
            with self.subTest(node_id=original["node_id"]):
                if original["kind"] == "relation_root_paper":
                    self.assertEqual(nodes[original["node_id"]], {**original, "kind": "structured_paper", "trust_status": fact_trust})
                else:
                    self.assertEqual(nodes[original["node_id"]], original)
        self.assertEqual(nodes["paper:fact-only"]["kind"], "structured_paper")

    def test_graph_distinguishes_candidates_evidence_and_bibliographic_edges(self) -> None:
        mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_graph")
        evidence = [{
            "evidence_id": "evidence_1", "claim": "Reviewed claim", "provenance": {
                "document_id": "paper_1", "source": "fixture", "access_policy": "oa"
            }
        }]
        graph = _literature_graph_projection(
            mission,
            evidence,
            [{"document_id": "paper_1", "title": "Paper one", "source": "Sciverse", "publication_year": 2025, "is_content_accessible": True}],
            {
                "source": {"document_id": "paper_1"},
                "edges": [{"edge_type": "citation_reference", "target_openalex_id": "https://openalex.org/W2"}],
            },
            {
                "source": {"document_id": "paper_1"},
                "edges": [{"edge_type": "crossref_reference", "target_doi": "10.1000/target"}],
            },
            None,
            citation_expansion={
                "trust_status": "public_bibliographic_metadata_not_scientific_evidence",
                "nodes": [{"doi": "10.1000/root", "depth": 0}, {"doi": "10.1000/citing", "depth": 1}],
                "edges": [{"source_doi": "10.1000/citing", "target_doi": "10.1000/root", "edge_type": "citation_cited_by", "depth": 1}],
            },
        )
        node_kinds = {node["kind"] for node in graph["nodes"]}
        edge_kinds = {edge["edge_type"] for edge in graph["edges"]}
        self.assertTrue({"mission", "candidate_paper", "accepted_evidence", "openalex_work", "crossref_work", "citation_work"} <= node_kinds)
        self.assertTrue({"retrieval_candidate", "source_provenance", "citation_reference", "citation_cited_by", "crossref_reference"} <= edge_kinds)
        self.assertIn("not_a_scientific_conclusion", graph["trust_status"])
        condition_graph = _literature_graph_projection(
            mission, evidence, [], None, None, None,
            condition_matrix=[dict(
                condition_cluster="matched strain and thickness",
                supporting_evidence_ids=["evidence_1"],
                contradicting_evidence_ids=["evidence_1"],
                differing_fields=["method"],
                unknowns=["oxygen_pressure"],
            )],
        )
        cluster = next(node for node in condition_graph["nodes"] if node["kind"] == "condition_cluster")
        self.assertEqual(cluster["trust_status"], "derived_condition_comparison_not_scientific_conclusion")
        condition_edges = list(edge for edge in condition_graph["edges"] if edge["target_id"] == cluster["node_id"])
        self.assertEqual(sorted(edge["edge_type"] for edge in condition_edges), ["condition_contradiction", "condition_support"])


if __name__ == "__main__":
    unittest.main()

