import unittest

from cosmatter.candidate_route_facets import classify_candidate_route
from cosmatter.models import MissionBrief


class CandidateRouteFacetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief(
            mission_id="mission_pst_facets",
            question="固定组分 (Pb_xSr_1-x)TiO3 构型怎样优化介电和压电性质？性质只能由分子动力学模拟获得，不存在性质预测的代理模型。",
            material="(Pb_xSr_1-x)TiO3",
            property_name="dielectric and piezoelectric response",
            scope="8x8x8 A-site configuration search with MD-only property evaluation",
        )

    def test_exact_pst_title_is_separate_from_single_endmember_analogue(self) -> None:
        exact = classify_candidate_route(self.mission, {"title": "A-site ordering in lead strontium titanate solid solutions"}, approved_counterevidence_query=False)
        analogue = classify_candidate_route(self.mission, {"title": "Domain response in SrTiO3 perovskites"}, approved_counterevidence_query=False)

        self.assertEqual(exact["research_track"], "exact_material")
        self.assertIn("exact_material_title", exact["facet_signals"])
        self.assertEqual(analogue["research_track"], "mechanism_analogue")
        self.assertNotIn("exact_material_title", analogue["facet_signals"])

    def test_search_method_is_an_algorithm_track_without_becoming_evidence(self) -> None:
        result = classify_candidate_route(self.mission, {"title": "Replica exchange Monte Carlo for combinatorial configuration search"}, approved_counterevidence_query=False)

        self.assertEqual(result["research_track"], "algorithm")
        self.assertEqual(result["route_eligibility"], "primary_allowed")
        self.assertIn("configuration_search_method", result["facet_signals"])

    def test_property_surrogate_is_counterevidence_only_when_mission_forbids_it(self) -> None:
        result = classify_candidate_route(self.mission, {"title": "Bayesian optimization with a Gaussian process surrogate model for dielectric properties"}, approved_counterevidence_query=False)

        self.assertEqual(result["research_track"], "algorithm")
        self.assertEqual(result["route_eligibility"], "counterevidence_only")
        self.assertIn("property_surrogate_method", result["facet_signals"])
        self.assertIn("mission_forbids_property_surrogate", result["facet_signals"])

    def test_md_is_not_misclassified_as_a_property_surrogate(self) -> None:
        result = classify_candidate_route(self.mission, {"title": "Molecular dynamics simulation of ferroelectric domain switching"}, approved_counterevidence_query=False)

        self.assertEqual(result["route_eligibility"], "primary_allowed")
        self.assertIn("molecular_dynamics_method", result["facet_signals"])
        self.assertNotIn("property_surrogate_method", result["facet_signals"])

    def test_approved_counter_query_remains_counterevidence_only(self) -> None:
        result = classify_candidate_route(self.mission, {"title": "A-site ordering in PbSrTiO3 perovskites"}, approved_counterevidence_query=True)

        self.assertEqual(result["route_eligibility"], "counterevidence_only")
        self.assertIn("approved_counterevidence_query", result["facet_signals"])


if __name__ == "__main__":
    unittest.main()
