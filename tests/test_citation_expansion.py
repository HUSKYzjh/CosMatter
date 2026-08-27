import unittest

from cosmatter.citation_expansion import MAX_NODES, build_citation_expansion


class CitationExpansionTests(unittest.TestCase):
    def test_two_hop_bidirectional_graph_is_bounded_and_not_evidence(self):
        graph = {
            "10.1/root": {"references": ["10.1/a", "10.1/b"], "cited_by": ["10.1/c"]},
            "10.1/a": {"references": ["10.1/d"], "cited_by": []},
            "10.1/b": {"references": [], "cited_by": ["10.1/e"]},
            "10.1/c": {"references": [], "cited_by": []},
        }
        result = build_citation_expansion("mission_1", "doi:10.1/root", lambda doi: graph.get(doi, {}))
        self.assertEqual(result["trust_status"], "public_bibliographic_metadata_not_scientific_evidence")
        self.assertLessEqual(len(result["nodes"]), MAX_NODES)
        self.assertTrue(any(item["doi"] == "10.1/d" and item["depth"] == 2 for item in result["nodes"]))

