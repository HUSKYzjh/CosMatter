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
from tools.build_private_bfo_indicator_shortlist import PROJECT_ROOT, build


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


if __name__ == "__main__":
    unittest.main()
