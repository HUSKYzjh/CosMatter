import copy
import sqlite3
import unittest

from cosmatter.config import AGENT_ROOT
from cosmatter.material_indicator_registry import (
    MaterialIndicatorRegistryError,
    QUALIFIER_FIELDS,
    load_material_indicator_catalog,
    load_material_observation_set,
    validate_material_observation_set,
)


class MaterialIndicatorRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_path = AGENT_ROOT / "configs" / "bfo_p0_material_indicator_catalog.json"
        self.seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_p0_literature_observation_candidates.json"
        self.catalog = load_material_indicator_catalog(self.catalog_path)
        self.seed = load_material_observation_set(self.seed_path, self.catalog)

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
