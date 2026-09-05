import copy
import sqlite3
import unittest

from cosmatter.config import AGENT_ROOT
from cosmatter.material_indicator_registry import (
    MaterialIndicatorRegistryError,
    QUALIFIER_FIELDS,
    load_material_indicator_catalog,
    load_material_observation_set,
    load_material_source_candidate_matrix,
    validate_material_observation_set,
    validate_material_source_candidate_matrix,
)


class MaterialIndicatorRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_path = AGENT_ROOT / "configs" / "bfo_p0_material_indicator_catalog.json"
        self.seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_p0_literature_observation_candidates.json"
        self.source_matrix_path = AGENT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json"
        self.catalog = load_material_indicator_catalog(self.catalog_path)
        self.seed = load_material_observation_set(self.seed_path, self.catalog)
        self.source_matrix = load_material_source_candidate_matrix(self.source_matrix_path, self.catalog)

    def test_p0_catalog_freezes_four_families_and_twelve_qualifiers(self) -> None:
        self.assertEqual(
            tuple(item["field_id"] for item in self.catalog["qualifier_fields"]),
            QUALIFIER_FIELDS,
        )
        self.assertEqual(
            {item["family"] for item in self.catalog["indicators"]},
            {"structure_phase", "ferroelectric", "electrical_transport", "phase_transition"},
        )
        self.assertTrue(all(item["priority"] == "P0" for item in self.catalog["indicators"]))

    def test_polarization_and_coercive_field_semantics_are_distinct(self) -> None:
        ids = {item["indicator_id"] for item in self.catalog["indicators"]}
        self.assertTrue({
            "spontaneous_polarization_ps", "remanent_polarization_pr",
            "switched_polarization_2pr", "coercive_field_ec", "coercive_field_2ec",
        }.issubset(ids))
        self.assertNotIn("polarization", ids)
        self.assertNotIn("coercive_field", ids)

    def test_conductive_wall_fraction_is_not_domain_wall_conductivity(self) -> None:
        indicators = {
            item["indicator_id"]: item for item in self.catalog["indicators"]
        }
        fraction = indicators["conductive_domain_wall_fraction"]
        conductivity = indicators["domain_wall_conductivity"]
        self.assertEqual(fraction["quantity_kind"], "fraction")
        self.assertEqual(fraction["canonical_unit"], "percent")
        self.assertEqual(conductivity["quantity_kind"], "conductivity")
        self.assertEqual(conductivity["canonical_unit"], "S/cm")

    def test_seed_observations_are_explicitly_unreviewed_literature_leads(self) -> None:
        self.assertEqual(
            self.seed["trust_status"],
            "candidate_literature_observations_not_human_data_checked",
        )
        self.assertGreaterEqual(len(self.seed["observations"]), 8)
        for item in self.seed["observations"]:
            self.assertEqual(tuple(item["qualifiers"]), QUALIFIER_FIELDS)
            self.assertEqual(item["maturity_level"], "literature_mentioned")
            self.assertEqual(item["assessment_authority"], "unreviewed")
            self.assertEqual(item["source_map_status"], "none")
            self.assertEqual(item["data_status"], "not_checked")
            self.assertIsNone(item["segment_id"])
            self.assertIsNone(item["locator"])
            self.assertIsNone(item["source_quote_sha256"])

    def test_conductive_wall_fractions_remain_separate_condition_bound_observations(self) -> None:
        observations = [
            item for item in self.seed["observations"]
            if item["indicator_id"] == "conductive_domain_wall_fraction"
        ]
        self.assertEqual([item["reported_value"] for item in observations], [69, 22, 59])
        self.assertEqual({item["reported_unit"] for item in observations}, {"percent"})
        self.assertEqual(len({item["qualifiers"]["preparation"] for item in observations}), 3)
        self.assertTrue(all(
            "not an absolute" in item["limitation"]
            or "not an S/cm" in item["limitation"]
            or "universal" in item["limitation"]
            for item in observations
        ))

    def test_missing_qualifier_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.seed)
        del candidate["observations"][0]["qualifiers"]["temperature"]
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "twelve ordered qualifier"):
            validate_material_observation_set(candidate, self.catalog)

    def test_candidate_set_cannot_launder_a_value_into_data_supported(self) -> None:
        candidate = copy.deepcopy(self.seed)
        candidate["observations"][0]["maturity_level"] = "data_supported"
        candidate["observations"][0]["assessment_authority"] = "human_data_review"
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "candidate observations cannot claim"):
            validate_material_observation_set(candidate, self.catalog)

    def test_unmapped_observation_cannot_claim_source_binding(self) -> None:
        candidate = copy.deepcopy(self.seed)
        candidate["observations"][0]["segment_id"] = "segment_001"
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "cannot claim Source Map"):
            validate_material_observation_set(candidate, self.catalog)

    def test_known_unit_normalization_cannot_change_a_reported_value(self) -> None:
        candidate = copy.deepcopy(self.seed)
        observation = candidate["observations"][0]
        observation["normalized_lower"] = 500
        observation["normalized_upper"] = 600
        observation["normalized_unit"] = "uC/cm2"
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "normalized value does not match"):
            validate_material_observation_set(candidate, self.catalog)

    def test_each_p0_question_has_independent_support_and_a_counterexample(self) -> None:
        self.assertEqual(len(self.source_matrix["questions"]), 4)
        for question in self.source_matrix["questions"]:
            roles = {item["role"] for item in question["source_candidates"]}
            self.assertEqual(
                roles,
                {"primary_support", "independent_support", "boundary_counterexample"},
            )
            primary = next(item for item in question["source_candidates"] if item["role"] == "primary_support")
            independent = next(item for item in question["source_candidates"] if item["role"] == "independent_support")
            self.assertNotEqual(primary["independence_group"], independent["independence_group"])

    def test_source_matrix_records_the_bounded_sciverse_content_probe(self) -> None:
        self.assertEqual(self.source_matrix["provider_probe_summary"], {
            "provider": "sciverse",
            "operation": "semantic_search_and_bounded_content",
            "search_status": "succeeded",
            "content_status": "succeeded",
            "probe_scope": "polarization_route_only_no_source_text_persisted",
        })

    def test_public_fulltext_batch_is_parsed_but_not_promoted_to_evidence(self) -> None:
        sources = [
            source
            for question in self.source_matrix["questions"]
            for source in question["source_candidates"]
        ]
        ready = [source for source in sources if source["access_status"] == "private_mineru_review_pool_ready"]
        self.assertEqual(len(ready), 6)
        self.assertEqual(
            {source["source_id"] for source in ready},
            {
                "arnold2009_prl_027602",
                "bencan2020_ncomms15595",
                "lebeugle2007_apl_2753390",
                "sando2016_ncomms10718",
                "teague1970_ssc_90262",
                "zeches2009_science_1177046",
            },
        )
        self.assertNotIn("institutional_access_required", {source["fulltext_route"] for source in ready})
        self.assertTrue(all(source["evidence_status"] == "metadata_or_abstract_checked_not_source_mapped" for source in ready))

    def test_source_matrix_rejects_false_independence_and_evidence_promotion(self) -> None:
        candidate = copy.deepcopy(self.source_matrix)
        sources = candidate["questions"][0]["source_candidates"]
        sources[1]["independence_group"] = sources[0]["independence_group"]
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "distinct independence groups"):
            validate_material_source_candidate_matrix(candidate, self.catalog)

        candidate = copy.deepcopy(self.source_matrix)
        candidate["questions"][0]["source_candidates"][0]["evidence_status"] = "human_reviewed"
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "cannot claim reviewed evidence"):
            validate_material_source_candidate_matrix(candidate, self.catalog)

    def test_source_matrix_rejects_urls_in_public_candidate_text(self) -> None:
        candidate = copy.deepcopy(self.source_matrix)
        candidate["questions"][0]["source_candidates"][0]["claim_boundary"] = "See https://example.invalid"
        with self.assertRaisesRegex(MaterialIndicatorRegistryError, "public text"):
            validate_material_source_candidate_matrix(candidate, self.catalog)

    def test_relational_template_creates_bounded_observation_tables(self) -> None:
        schema = (AGENT_ROOT / "docs" / "templates" / "material_observation_registry.sql").read_text(encoding="utf-8")
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        finally:
            connection.close()
        self.assertTrue({
            "material_indicator_catalog", "material_indicator_qualifier_definition",
            "material_indicator_definition", "material_indicator_allowed_unit",
            "material_indicator_required_qualifier", "material_observation_set",
            "material_observation", "material_observation_qualifier",
        }.issubset(tables))
        lowered = schema.casefold()
        self.assertNotIn("api_key", lowered)
        self.assertNotIn("authorization", lowered)
        self.assertNotIn("file://", lowered)


if __name__ == "__main__":
    unittest.main()
