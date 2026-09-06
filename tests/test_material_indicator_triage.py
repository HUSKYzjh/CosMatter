from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.material_indicator_triage import (
    MaterialIndicatorTriageError,
    SHORTLIST_TRUST_STATUS,
    build_private_indicator_shortlist,
)
from tools.build_private_bfo_indicator_shortlist import PROJECT_ROOT, build, build_from_manifest


class MaterialIndicatorTriageTests(unittest.TestCase):
    def _matrix(self, document_ids: tuple[str, ...] = ("paper_a",)) -> dict:
        return {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-p0-experimental-indicators/v1",
            "material_scope": "BiFeO3",
            "questions": [
                {
                    "question_id": "polarization",
                    "focus_indicator_ids": ["spontaneous_polarization_ps", "hysteresis_saturation"],
                    "source_candidates": [
                        {
                            "source_id": document_id,
                            "role": "primary_support",
                            "access_status": "private_mineru_review_pool_ready",
                        }
                        for document_id in document_ids
                    ],
                }
            ],
        }

    def _pool(self, document_id: str, digest: str, segments: list[tuple[str, str]]) -> dict:
        return {
            "document_id": document_id,
            "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
            "source_markdown_sha256": digest,
            "candidate_segments": [
                {"segment_id": identifier, "locator": f"markdown_line:{index}-{index}", "kind": "paragraph", "quote": quote}
                for index, (identifier, quote) in enumerate(segments, 1)
            ],
        }

    def _index(self, document_ids: tuple[str, ...], digest: str) -> dict:
        return {
            "mission_id": "bfo-test",
            "trust_status": "private_unreviewed_mineru_manifest_review_index_not_evidence",
            "entries": [{"document_id": document_id, "markdown_sha256": digest} for document_id in document_ids],
        }

    def test_prefers_indicator_value_with_conditions_and_is_hash_bound(self) -> None:
        digest = "a" * 64
        result = build_private_indicator_shortlist(
            matrix=self._matrix(),
            review_index=self._index(("paper_a",), digest),
            pools_by_document={
                "paper_a": self._pool(
                    "paper_a",
                    digest,
                    [
                        ("seg_1", "BiFeO3 is a multiferroic material."),
                        ("seg_2", "At room temperature the measured spontaneous polarization was 60 μC/cm2 along [012]."),
                        ("seg_3", "The hysteresis loop became unsaturated after cycling degradation."),
                    ],
                )
            },
        )
        self.assertEqual(result["trust_status"], SHORTLIST_TRUST_STATUS)
        self.assertEqual(result["segment_count"], 2)
        first = result["documents"][0]["segments"][0]
        self.assertEqual(first["segment_id"], "seg_2")
        self.assertIn("spontaneous_polarization_ps", first["matched_indicator_ids"])
        self.assertIn("reported_value_candidate", first["candidate_roles"])
        self.assertEqual(first["quote_sha256"], hashlib.sha256(first["quote"].encode()).hexdigest())

    def test_penalizes_reference_entries_and_is_deterministic(self) -> None:
        digest = "b" * 64
        pool = self._pool(
            "paper_a",
            digest,
            [
                ("ref", "References\n1 Smith et al. Polarization 60 μC/cm2 thin film 2020."),
                ("body", "We measured the polarization loop at 60 Hz and 77 K."),
                ("limit", "However, the hysteresis loop was unsaturated at the maximum field."),
            ],
        )
        arguments = dict(matrix=self._matrix(), review_index=self._index(("paper_a",), digest), pools_by_document={"paper_a": pool})
        first = build_private_indicator_shortlist(**arguments)
        second = build_private_indicator_shortlist(**arguments)
        self.assertEqual(first, second)
        identifiers = [item["segment_id"] for item in first["documents"][0]["segments"]]
        self.assertNotIn("ref", identifiers)

    def test_mineru_tex_spaced_value_and_unit_are_ranked(self) -> None:
        digest = "f" * 64
        result = build_private_indicator_shortlist(
            matrix=self._matrix(),
            review_index=self._index(("paper_a",), digest),
            pools_by_document={
                "paper_a": self._pool(
                    "paper_a",
                    digest,
                    [
                        ("plain", "The spontaneous polarization was discussed."),
                        ("tex", r"The measured spontaneous polarization was $6 0 \ \mu \mathrm { C . c m } ^ { - 2 }$ at room temperature."),
                    ],
                )
            },
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertEqual(selected["segment_id"], "tex")
        self.assertIn("numeric_or_unit_expression", selected["reason_codes"])

    def test_primary_result_language_beats_background_comparison(self) -> None:
        digest = "1" * 64
        result = build_private_indicator_shortlist(
            matrix=self._matrix(),
            review_index=self._index(("paper_a",), digest),
            pools_by_document={
                "paper_a": self._pool(
                    "paper_a",
                    digest,
                    [
                        ("background", "Recently a spontaneous polarization of 90 uC/cm2 was observed in thin films."),
                        ("result", "From our measurement we extract a spontaneous polarization of 60 uC/cm2 at room temperature."),
                    ],
                )
            },
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertEqual(selected["segment_id"], "result")
        self.assertIn("primary_result_language", selected["reason_codes"])

    def test_indicator_compatible_unit_beats_unrelated_energy_value(self) -> None:
        digest = "2" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-p0-experimental-indicators/v1",
            "material_scope": "BiFeO3",
            "questions": [
                {
                    "question_id": "strain",
                    "focus_indicator_ids": ["epitaxial_strain", "tetragonality_c_over_a"],
                    "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
                }
            ],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={
                "paper_a": self._pool(
                    "paper_a",
                    digest,
                    [
                        ("energy", "The band gap was 2.6 eV and correlated with epitaxial strain and c/a."),
                        ("ratio", r"Under epitaxial strain the measured c/a ratio was $1 . 2 6$."),
                    ],
                )
            },
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertEqual(selected["segment_id"], "ratio")
        self.assertIn("indicator_compatible_value_or_unit", selected["reason_codes"])

    def test_c_over_a_change_range_is_indicator_compatible(self) -> None:
        digest = "3" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-p0-experimental-indicators/v1",
            "material_scope": "BiFeO3",
            "questions": [{
                "question_id": "ratio", "focus_indicator_ids": ["tetragonality_c_over_a"],
                "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
            }],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={"paper_a": self._pool(
                "paper_a", digest,
                [("ratio", "Thus, the c/a ratio changes from 1.07 for the R phase to 1.27 in the T phase over 10 unit cells.")],
            )},
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertIn("indicator_compatible_value_or_unit", selected["reason_codes"])
        self.assertIn("numeric_range_expression", selected["reason_codes"])

    def test_domain_wall_fraction_beats_ac_voltage_method_settings(self) -> None:
        digest = "4" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-p0-experimental-indicators/v1",
            "material_scope": "BiFeO3",
            "questions": [{
                "question_id": "walls", "focus_indicator_ids": ["domain_wall_conductivity", "conductive_domain_wall_fraction"],
                "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
            }],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={"paper_a": self._pool(
                "paper_a", digest,
                [
                    ("settings", "c-AFM used 8 V a.c. voltage and a d.c. bias from 7 to 17 V."),
                    ("fractions", "Fractions of DWs exhibiting current signals were 69% pristine, 22% quenched, and 59% aged."),
                ],
            )},
            max_segments_per_document=1,
        )
        self.assertEqual(result["documents"][0]["segments"][0]["segment_id"], "fractions")
        self.assertIn(
            "indicator_compatible_value_or_unit",
            result["documents"][0]["segments"][0]["reason_codes"],
        )

    def test_magnetic_abbreviations_and_units_are_indicator_compatible(self) -> None:
        digest = "5" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-experimental-indicators/v2",
            "material_scope": "BiFeO3",
            "questions": [{
                "question_id": "magnetism",
                "focus_indicator_ids": ["saturation_magnetization_ms", "magnetic_coercive_field_hc"],
                "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
            }],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={"paper_a": self._pool(
                "paper_a", digest,
                [
                    ("generic", "Magnetic properties were measured at room temperature."),
                    ("loop", "The 70 nm film has Ms = 150 emu/cm3 and Hc = 200 Oe at room temperature."),
                ],
            )},
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertEqual(selected["segment_id"], "loop")
        self.assertEqual(
            selected["matched_indicator_ids"],
            ["saturation_magnetization_ms", "magnetic_coercive_field_hc"],
        )
        self.assertIn("indicator_compatible_value_or_unit", selected["reason_codes"])

    def test_photovoltaic_signs_and_microampere_density_are_ranked(self) -> None:
        digest = "6" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-experimental-indicators/v2",
            "material_scope": "BiFeO3",
            "questions": [{
                "question_id": "photovoltaic",
                "focus_indicator_ids": ["open_circuit_voltage", "short_circuit_current_density"],
                "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
            }],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={"paper_a": self._pool(
                "paper_a", digest,
                [
                    ("voltage", "The photovoltaic response was discussed."),
                    ("signed", r"Under 375 nm illumination, the open-circuit voltage is -0.23 V and the short-circuit current is $+5 7 \mu \mathrm { A } / \mathrm { c m } ^ { 2 }$ after downward poling."),
                ],
            )},
            max_segments_per_document=1,
        )
        selected = result["documents"][0]["segments"][0]
        self.assertEqual(selected["segment_id"], "signed")
        self.assertEqual(
            selected["matched_indicator_ids"],
            ["open_circuit_voltage", "short_circuit_current_density"],
        )
        self.assertIn("indicator_compatible_value_or_unit", selected["reason_codes"])

    def test_deposition_rate_and_explicit_batch_count_are_ranked(self) -> None:
        digest = "7" * 64
        matrix = {
            "schema_version": "cosmatter.material-source-candidate-matrix/v1",
            "catalog_id": "bfo-experimental-indicators/v2",
            "material_scope": "BiFeO3",
            "questions": [{
                "question_id": "process",
                "focus_indicator_ids": ["deposition_rate", "replicate_batch_count"],
                "source_candidates": [{"source_id": "paper_a", "role": "primary_support", "access_status": "private_mineru_review_pool_ready"}],
            }],
        }
        result = build_private_indicator_shortlist(
            matrix=matrix,
            review_index=self._index(("paper_a",), digest),
            pools_by_document={"paper_a": self._pool(
                "paper_a", digest,
                [
                    ("rate", "The measured growth rate was 0.80 angstrom/s at 700 deg C."),
                    ("batches", "Three batches comprising 17 total specimens were sintered at 745, 760 and 780 deg C."),
                ],
            )},
        )
        selected = result["documents"][0]["segments"]
        self.assertEqual({item["segment_id"] for item in selected}, {"rate", "batches"})
        self.assertTrue(all("indicator_compatible_value_or_unit" in item["reason_codes"] for item in selected))

    def test_total_cap_preserves_one_segment_per_document_before_seconds(self) -> None:
        digest = "c" * 64
        document_ids = tuple(f"paper_{index}" for index in range(7))
        pools = {
            document_id: self._pool(
                document_id,
                digest,
                [
                    ("best", "Measured spontaneous polarization was 70 μC/cm2 at room temperature."),
                    ("second", "The hysteresis loop was saturated at 50 kV/cm."),
                ],
            )
            for document_id in document_ids
        }
        result = build_private_indicator_shortlist(
            matrix=self._matrix(document_ids),
            review_index=self._index(document_ids, digest),
            pools_by_document=pools,
            max_total_segments=7,
        )
        self.assertEqual(result["document_count"], 7)
        self.assertEqual(result["segment_count"], 7)
        self.assertTrue(all(len(item["segments"]) == 1 for item in result["documents"]))

    def test_rejects_pool_hash_mismatch(self) -> None:
        with self.assertRaisesRegex(MaterialIndicatorTriageError, "hash"):
            build_private_indicator_shortlist(
                matrix=self._matrix(),
                review_index=self._index(("paper_a",), "d" * 64),
                pools_by_document={"paper_a": self._pool("paper_a", "e" * 64, [("seg", "Polarization was 1 μC/cm2.")])},
            )

    def test_writer_keeps_private_output_outside_repository(self) -> None:
        with self.assertRaisesRegex(MaterialIndicatorTriageError, "outside the repository"):
            build(
                matrix_path=PROJECT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json",
                review_index_path=PROJECT_ROOT / "private-index.json",
                output_path=PROJECT_ROOT / "private-shortlist.json",
            )

    def test_writer_rejects_an_unversioned_matrix_even_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(MaterialIndicatorTriageError, "supported versioned"):
                build(
                    matrix_path=root / "matrix.json",
                    review_index_path=root / "private-index.json",
                    output_path=root / "private-shortlist.json",
                )

    def test_full_manifest_route_ranks_value_missing_from_sampled_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown_root = root / "markdown"
            markdown_root.mkdir()
            markdown = markdown_root / "paper.md"
            filler = "\n\n".join(f"Unrelated paragraph {index}." for index in range(80))
            markdown.write_text(
                filler + "\n\nAt room temperature the measured spontaneous polarization was 60 μC/cm2 along [012].",
                encoding="utf-8",
            )
            digest = hashlib.sha256(markdown.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "private_output_only": True,
                        "entries": [
                            {
                                "status": "downloaded",
                                "source_relative_path": "lebeugle2007_apl_2753390.pdf",
                                "markdown_relative_path": "paper.md",
                                "markdown_sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            matrix_path = PROJECT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json"
            result = build_from_manifest(
                matrix_path=matrix_path,
                manifest_path=manifest,
                markdown_root=markdown_root,
                output_path=root / "shortlist.json",
            )
            self.assertEqual(result["selection_method"], "deterministic_full_markdown_indicator_numeric_condition_ranking_v2")
            self.assertEqual(result["documents"][0]["document_id"], "lebeugle2007_apl_2753390")
            self.assertIn("60 μC/cm2", result["documents"][0]["segments"][0]["quote"])

    def test_full_manifest_route_accepts_the_versioned_magnetic_value_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown_root = root / "markdown"
            markdown_root.mkdir()
            markdown = markdown_root / "wang.md"
            markdown.write_text(
                "At room temperature the 70 nm film has Ms = 150 emu/cm3 and Hc = 200 Oe.",
                encoding="utf-8",
            )
            digest = hashlib.sha256(markdown.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "private_output_only": True,
                        "entries": [{
                            "status": "downloaded",
                            "source_relative_path": "wang2003.pdf",
                            "markdown_relative_path": "wang.md",
                            "markdown_sha256": digest,
                        }],
                    }
                ),
                encoding="utf-8",
            )
            result = build_from_manifest(
                matrix_path=PROJECT_ROOT / "configs" / "bfo_magnetic_pv_process_source_candidate_matrix_v2.json",
                manifest_path=manifest,
                markdown_root=markdown_root,
                output_path=root / "shortlist.json",
            )
            self.assertEqual(result["documents"][0]["document_id"], "wang2003")
            self.assertEqual(
                result["documents"][0]["segments"][0]["matched_indicator_ids"],
                ["saturation_magnetization_ms", "magnetic_coercive_field_hc"],
            )


if __name__ == "__main__":
    unittest.main()
