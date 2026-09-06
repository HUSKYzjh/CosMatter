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
    validate_material_indicator_catalog,
    validate_material_observation_set,
    validate_material_source_candidate_matrix,
)


class MaterialIndicatorRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_path = AGENT_ROOT / "configs" / "bfo_p0_material_indicator_catalog.json"
        self.expanded_catalog_path = AGENT_ROOT / "configs" / "bfo_experimental_indicator_catalog_v2.json"
        self.seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_p0_literature_observation_candidates.json"
        self.expanded_seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_expanded_literature_observation_candidates_v2.json"
        self.remaining_seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_magnetic_optical_process_literature_observation_candidates_v2.json"
        self.value_seed_path = AGENT_ROOT / "examples" / "frozen" / "bfo_magnetic_pv_process_literature_observation_candidates_v2.json"
        self.source_matrix_path = AGENT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json"
        self.expanded_source_matrix_path = AGENT_ROOT / "configs" / "bfo_expanded_source_candidate_matrix_v2.json"
        self.remaining_source_matrix_path = AGENT_ROOT / "configs" / "bfo_magnetic_optical_process_source_candidate_matrix_v2.json"
        self.value_source_matrix_path = AGENT_ROOT / "configs" / "bfo_magnetic_pv_process_source_candidate_matrix_v2.json"
        self.catalog = load_material_indicator_catalog(self.catalog_path)
        self.expanded_catalog = load_material_indicator_catalog(self.expanded_catalog_path)
        self.seed = load_material_observation_set(self.seed_path, self.catalog)
        self.expanded_seed = load_material_observation_set(
            self.expanded_seed_path,
            self.expanded_catalog,
        )
        self.remaining_seed = load_material_observation_set(
            self.remaining_seed_path,
            self.expanded_catalog,
        )
        self.value_seed = load_material_observation_set(
            self.value_seed_path,
            self.expanded_catalog,
        )
        self.source_matrix = load_material_source_candidate_matrix(self.source_matrix_path, self.catalog)
        self.expanded_source_matrix = load_material_source_candidate_matrix(
            self.expanded_source_matrix_path,
            self.expanded_catalog,
        )
        self.remaining_source_matrix = load_material_source_candidate_matrix(
            self.remaining_source_matrix_path,
            self.expanded_catalog,
        )
        self.value_source_matrix = load_material_source_candidate_matrix(
            self.value_source_matrix_path,
            self.expanded_catalog,
        )

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

    def test_v2_catalog_is_a_strict_superset_with_all_priority_tiers(self) -> None:
        p0_ids = {item["indicator_id"] for item in self.catalog["indicators"]}
        expanded_ids = {
            item["indicator_id"] for item in self.expanded_catalog["indicators"]
        }
        self.assertTrue(p0_ids.issubset(expanded_ids))
        self.assertEqual(
            {item["family"] for item in self.expanded_catalog["indicators"]},
            {
                "structure_phase", "ferroelectric", "electrical_transport",
                "phase_transition", "dielectric_piezoelectric", "magnetic",
                "optical_photovoltaic", "defect_chemistry",
                "process_reproducibility",
            },
        )
        self.assertEqual(
            {item["priority"] for item in self.expanded_catalog["indicators"]},
            {"P0", "P1", "P2"},
        )

    def test_v2_catalog_rejects_an_unknown_priority(self) -> None:
        candidate = copy.deepcopy(self.expanded_catalog)
        candidate["indicators"][-1]["priority"] = "P3"
        with self.assertRaisesRegex(
            MaterialIndicatorRegistryError,
            "family, priority, or category",
        ):
            validate_material_indicator_catalog(candidate)

    def test_v2_catalog_requires_every_declared_priority_tier(self) -> None:
        candidate = copy.deepcopy(self.expanded_catalog)
        for indicator in candidate["indicators"]:
            if indicator["priority"] == "P2":
                indicator["priority"] = "P1"
        with self.assertRaisesRegex(
            MaterialIndicatorRegistryError,
            "cover every profile priority",
        ):
            validate_material_indicator_catalog(candidate)

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

    def test_direct_and_effective_d33_are_distinct_in_v2(self) -> None:
        indicators = {
            item["indicator_id"]: item
            for item in self.expanded_catalog["indicators"]
        }
        direct = indicators["piezoelectric_coefficient_d33"]
        effective = indicators["effective_piezoelectric_response_d33"]
        self.assertEqual(direct["canonical_unit"], "pC/N")
        self.assertEqual(effective["canonical_unit"], "pm/V")
        self.assertNotEqual(direct["quantity_kind"], effective["quantity_kind"])

    def test_expanded_leads_keep_method_and_condition_boundaries(self) -> None:
        observations = self.expanded_seed["observations"]
        self.assertEqual(len(observations), 7)
        self.assertTrue(all(item["source_map_status"] == "none" for item in observations))
        d33 = next(
            item for item in observations
            if item["indicator_id"] == "piezoelectric_coefficient_d33"
        )
        self.assertEqual((d33["reported_value"], d33["reported_uncertainty"]), (43, 6))
        self.assertEqual(d33["reported_unit"], "pC/N")
        eels = [
            item for item in observations
            if item["indicator_id"] == "eels_o_k_fe_l3_energy_separation"
        ]
        self.assertEqual([item["reported_value"] for item in eels], [179.3, 178.3])
        self.assertEqual(
            {item["qualifiers"]["measurement_geometry"] for item in eels},
            {
                "spectrum_acquired_inside_domain_wall_region",
                "spectrum_acquired_outside_domain_wall_region",
            },
        )

    def test_expanded_questions_have_independent_support_and_boundary_sources(self) -> None:
        self.assertEqual(len(self.expanded_source_matrix["questions"]), 4)
        for question in self.expanded_source_matrix["questions"]:
            by_role = {
                role: [
                    item for item in question["source_candidates"]
                    if item["role"] == role
                ]
                for role in (
                    "primary_support", "independent_support",
                    "boundary_counterexample",
                )
            }
            self.assertTrue(all(by_role.values()))
            primary_groups = {
                item["independence_group"] for item in by_role["primary_support"]
            }
            independent_groups = {
                item["independence_group"] for item in by_role["independent_support"]
            }
            self.assertTrue(primary_groups.isdisjoint(independent_groups))
            self.assertTrue(all(
                item["evidence_status"]
                == "metadata_or_abstract_checked_not_source_mapped"
                for item in question["source_candidates"]
            ))

    def test_expanded_sciverse_probe_does_not_claim_an_unrun_content_check(self) -> None:
        probe = self.expanded_source_matrix["provider_probe_summary"]
        self.assertEqual(probe["search_status"], "failed_closed")
        self.assertEqual(probe["content_status"], "not_attempted")
        self.assertIn("not_probed", probe["probe_scope"])

    def test_remaining_v2_families_have_independent_routes_and_real_bounded_probe(self) -> None:
        self.assertEqual(len(self.remaining_source_matrix["questions"]), 3)
        self.assertEqual(
            {question["question_id"] for question in self.remaining_source_matrix["questions"]},
            {
                "bfo_v2_spin_cycloid_period_boundary",
                "bfo_v2_optical_gap_definition_and_morphology_boundary",
                "bfo_v2_process_window_transferability",
            },
        )
        for question in self.remaining_source_matrix["questions"]:
            by_role = {
                role: [
                    source for source in question["source_candidates"]
                    if source["role"] == role
                ]
                for role in (
                    "primary_support", "independent_support",
                    "boundary_counterexample",
                )
            }
            self.assertTrue(all(by_role.values()))
            self.assertTrue(
                {source["independence_group"] for source in by_role["primary_support"]}
                .isdisjoint({
                    source["independence_group"]
                    for source in by_role["independent_support"]
                })
            )
        probe = self.remaining_source_matrix["provider_probe_summary"]
        self.assertEqual(
            (probe["search_status"], probe["content_status"]),
            ("succeeded", "succeeded"),
        )
        self.assertIn("one_500_character_window_each", probe["probe_scope"])
        self.assertIn("no_source_text_persisted", probe["probe_scope"])

    def test_remaining_v2_observations_keep_state_and_definition_boundaries(self) -> None:
        observations = self.remaining_seed["observations"]
        self.assertEqual(len(observations), 15)
        self.assertEqual(
            {item["indicator_id"] for item in observations},
            {
                "cycloid_period", "direct_band_gap", "indirect_band_gap",
                "growth_temperature", "oxygen_partial_pressure",
                "annealing_temperature",
            },
        )
        self.assertTrue(all(item["source_map_status"] == "none" for item in observations))
        self.assertTrue(all(item["data_status"] == "not_checked" for item in observations))
        self.assertTrue(all(item["maturity_level"] == "literature_mentioned" for item in observations))

        haykal = [
            item for item in observations
            if item["normalized_doi"] == "10.1038/s41467-020-15501-8"
        ]
        self.assertEqual([item["reported_value"] for item in haykal], [78, 65, 84])
        self.assertEqual(len({item["qualifiers"]["field_protocol"] for item in haykal}), 3)

        nanoparticle_gaps = [
            item for item in observations
            if item["normalized_doi"] == "10.1021/acs.jpcc.6b08548"
        ]
        self.assertEqual(
            [(item["indicator_id"], item["reported_value"]) for item in nanoparticle_gaps],
            [("direct_band_gap", 2.17), ("indirect_band_gap", 1.84)],
        )

        plumes = [
            item for item in observations
            if item["indicator_id"] == "oxygen_partial_pressure"
        ]
        self.assertEqual([item["reported_value"] for item in plumes], [0.01, 0.4])
        self.assertEqual({item["reported_unit"] for item in plumes}, {"mbar"})

    def test_magnetic_pv_process_matrix_has_independent_routes_and_batch_gap(self) -> None:
        self.assertEqual(len(self.value_source_matrix["questions"]), 5)
        self.assertEqual(
            {question["question_id"] for question in self.value_source_matrix["questions"]},
            {
                "bfo_v2_magnetic_loop_condition_boundary",
                "bfo_v2_absorption_coefficient_spectral_boundary",
                "bfo_v2_photovoltaic_geometry_illumination_boundary",
                "bfo_v2_deposition_rate_method_boundary",
                "bfo_v2_independent_batch_reporting_gap",
            },
        )
        for question in self.value_source_matrix["questions"]:
            by_role = {
                role: [
                    source for source in question["source_candidates"]
                    if source["role"] == role
                ]
                for role in (
                    "primary_support", "independent_support",
                    "boundary_counterexample",
                )
            }
            self.assertTrue(all(by_role.values()))
            self.assertTrue(
                {source["independence_group"] for source in by_role["primary_support"]}
                .isdisjoint({
                    source["independence_group"] for source in by_role["independent_support"]
                })
            )
        gap = next(
            question for question in self.value_source_matrix["questions"]
            if question["question_id"] == "bfo_v2_independent_batch_reporting_gap"
        )
        self.assertEqual(gap["focus_indicator_ids"], ["replicate_batch_count"])
        unreported = [
            source for source in gap["source_candidates"]
            if "no explicit" in source["reported_lead"].casefold()
        ]
        self.assertEqual(len(unreported), 2)
        self.assertTrue(all("batch" in source["reported_lead"].casefold() for source in unreported))
        explicit = next(
            source for source in gap["source_candidates"]
            if source["role"] == "boundary_counterexample"
        )
        self.assertEqual(explicit["normalized_doi"], "10.1038/s41467-018-07363-y")
        self.assertIn("three batches", explicit["reported_lead"].casefold())
        self.assertIn("17", explicit["reported_lead"])
        self.assertIn("not three independent repeats", explicit["claim_boundary"].casefold())
        ready = {
            source["source_id"]
            for question in self.value_source_matrix["questions"]
            for source in question["source_candidates"]
            if source["access_status"] == "private_mineru_review_pool_ready"
        }
        self.assertEqual(ready, {"wang2003", "mazumder2007", "zhou2020"})
        probe = self.value_source_matrix["provider_probe_summary"]
        self.assertEqual(
            (probe["search_status"], probe["content_status"]),
            ("succeeded", "succeeded"),
        )
        self.assertIn("five_indicator_queries", probe["probe_scope"])
        self.assertIn("no_source_text_or_provider_ids_persisted", probe["probe_scope"])

    def test_magnetic_pv_process_values_preserve_units_signs_and_conditions(self) -> None:
        observations = self.value_seed["observations"]
        self.assertEqual(len(observations), 25)
        self.assertTrue(all(item["source_map_status"] == "none" for item in observations))
        self.assertTrue(all(item["data_status"] == "not_checked" for item in observations))
        self.assertTrue(all(item["maturity_level"] == "literature_mentioned" for item in observations))
        batches = [item for item in observations if item["indicator_id"] == "replicate_batch_count"]
        self.assertEqual(len(batches), 1)
        self.assertEqual(
            (batches[0]["reported_value"], batches[0]["reported_unit"], batches[0]["normalized_doi"]),
            (3, "batch", "10.1038/s41467-018-07363-y"),
        )
        self.assertIn("three different sintering temperatures", batches[0]["limitation"])

        mazumder = [
            item for item in observations
            if item["normalized_doi"] == "10.1063/1.2768201"
        ]
        self.assertEqual(
            [
                (item["reported_value"], item["reported_unit"], item["qualifiers"]["thickness"])
                for item in mazumder
            ],
            [
                (0.41, "uB/Fe", "4_nm_particle_size"),
                (0.27, "uB/Fe", "15_nm_particle_size"),
                (0.13, "uB/Fe", "25_nm_particle_size"),
                (0.09, "uB/Fe", "40_nm_particle_size"),
            ],
        )

        wang = [
            item for item in observations
            if item["normalized_doi"] == "10.1126/science.1080615"
        ]
        self.assertEqual(
            [(item["indicator_id"], item["reported_value"], item["reported_unit"]) for item in wang],
            [
                ("saturation_magnetization_ms", 150, "emu/cm3"),
                ("magnetic_coercive_field_hc", 200, "Oe"),
                ("saturation_magnetization_ms", 5, "emu/cm3"),
            ],
        )
        zhou = [
            item for item in observations
            if item["normalized_doi"] == "10.1016/j.tsf.2020.137851"
        ]
        self.assertEqual(
            [(item["indicator_id"], item["reported_value"], item["reported_unit"]) for item in zhou],
            [
                ("open_circuit_voltage", 0.17, "V"),
                ("short_circuit_current_density", -0.61, "uA/cm2"),
                ("open_circuit_voltage", -0.23, "V"),
                ("short_circuit_current_density", 57, "uA/cm2"),
            ],
        )
        rates = [
            item for item in observations if item["indicator_id"] == "deposition_rate"
        ]
        self.assertEqual(
            [(item["value_semantics"], item["reported_value"], item["reported_lower"], item["reported_upper"], item["reported_unit"]) for item in rates],
            [
                ("exact", 0.8, None, None, "angstrom/s"),
                ("range", None, 4, 9, "nm/min"),
                ("exact", 0.03, None, None, "nm/min"),
            ],
        )

    def test_short_circuit_density_accepts_reported_micro_and_nano_units(self) -> None:
        indicator = next(
            item for item in self.expanded_catalog["indicators"]
            if item["indicator_id"] == "short_circuit_current_density"
        )
        self.assertEqual(
            indicator["allowed_reported_units"],
            ["A/cm2", "mA/cm2", "uA/cm2", "nA/cm2"],
        )

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
