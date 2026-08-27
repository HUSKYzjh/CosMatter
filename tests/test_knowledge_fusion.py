import unittest

from cosmatter.knowledge_fusion import fuse_reviewed_material_facts


def artifact(document_id: str, value: float, qualifiers: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0", "mission_id": "mission_fusion", "trust_status": "human_reviewed_structured_material_facts_not_scientific_conclusion", "document_id": document_id,
        "facts": [{"fact_id": f"fact_{document_id}", "segment_id": "seg_1", "category": "property", "name": "polarization", "value": value, "unit": "uC/cm2", "normalized_value": value, "normalized_unit": "uC/cm2", "qualifiers": qualifiers, "locator": "page:2", "source_quote_sha256": "a" * 64}],
    }


class KnowledgeFusionTests(unittest.TestCase):
    def test_marks_numeric_disagreement_only_when_qualifiers_match(self) -> None:
        result = fuse_reviewed_material_facts("mission_fusion", (artifact("doc_a", 50, {"temperature_k": 300}), artifact("doc_b", 60, {"temperature_k": 300})))
        row = result["comparisons"][0]
        self.assertEqual(row["comparison_status"], "value_disagreement_under_matching_qualifiers_requires_human_review")
        self.assertEqual([item["document_id"] for item in row["observations"]], ["doc_a", "doc_b"])

    def test_does_not_call_different_conditions_a_conflict(self) -> None:
        result = fuse_reviewed_material_facts("mission_fusion", (artifact("doc_a", 50, {"temperature_k": 300}), artifact("doc_b", 60, {"temperature_k": 350})))
        row = result["comparisons"][0]
        self.assertEqual(row["comparison_status"], "not_directly_comparable_differing_qualifiers")
        self.assertEqual(row["differing_qualifier_fields"], ["temperature_k"])


if __name__ == "__main__":
    unittest.main()
