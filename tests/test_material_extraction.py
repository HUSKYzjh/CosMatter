import hashlib
import tempfile
import unittest
from pathlib import Path

from cosmatter.material_extraction import MaterialExtractionError, iter_material_facts, load_material_facts, material_extraction_prompts, material_fact_review_template, material_facts_from_review, validate_material_fact_source_links, write_material_fact_review_template, write_material_facts, write_material_facts_for_document
from cosmatter.models import MissionBrief


QUOTE = "A strained BiFeO3 film was measured at 300 K."
SOURCE_MAP = {
    "schema_version": "1.0", "mission_id": "mission_material", "trust_status": "human_reviewed_parser_selection",
    "document_id": "doc_material", "provider": "mineru", "task_id_sha256": "a" * 64,
    "segments": [{"segment_id": "seg_1", "locator": "page:3 paragraph:2", "kind": "paragraph", "quote": QUOTE, "quote_sha256": hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()}],
}


def selection(segment_id: str = "seg_1") -> dict[str, object]:
    return {"document_id": "doc_material", "facts": [
        {"fact_id": "fact_comp", "segment_id": segment_id, "category": "composition", "name": "material", "value": "BiFeO3", "unit": None, "normalized_value": "BiFeO3", "normalized_unit": None, "qualifiers": {"sample_form": "film"}},
        {"fact_id": "fact_temp", "segment_id": segment_id, "category": "experimental_condition", "name": "temperature", "value": 300, "unit": "K", "normalized_value": 300, "normalized_unit": "K", "qualifiers": {"method": "reported measurement"}},
    ]}


class MaterialExtractionTests(unittest.TestCase):
    def test_reviewed_facts_keep_exact_source_map_provenance(self) -> None:
        artifact = material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=selection())
        self.assertEqual(artifact["facts"][1]["locator"], "page:3 paragraph:2")
        self.assertEqual(artifact["facts"][0]["source_quote_sha256"], SOURCE_MAP["segments"][0]["quote_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            path = write_material_facts(Path(directory), artifact)
            loaded = load_material_facts(path, "mission_material")
        self.assertEqual(loaded["facts"][0]["category"], "composition")

    def test_quote_free_review_template_must_match_current_source_map(self) -> None:
        template = material_fact_review_template(
            mission_id="mission_material", source_map=SOURCE_MAP,
        )
        self.assertEqual(template["trust_status"], "blank_human_material_fact_review_template_not_facts")
        self.assertNotIn(QUOTE, __import__("json").dumps(template))
        template["trust_status"] = "human_reviewed_material_facts_for_recording"
        template["facts"] = selection()["facts"]
        artifact = material_facts_from_review(
            mission_id="mission_material", source_map=SOURCE_MAP, selection=template,
        )
        self.assertEqual(artifact["facts"][0]["segment_id"], "seg_1")
        altered = {**template, "segments": [{**template["segments"][0], "locator": "page:9"}]}
        with self.assertRaises(MaterialExtractionError):
            material_facts_from_review(
                mission_id="mission_material", source_map=SOURCE_MAP, selection=altered,
            )
        with tempfile.TemporaryDirectory() as directory:
            path = write_material_fact_review_template(
                Path(directory), material_fact_review_template(
                    mission_id="mission_material", source_map=SOURCE_MAP,
                ),
            )
            self.assertTrue(path.exists())

    def test_document_scoped_storage_keeps_multiple_papers(self) -> None:
        first = material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=selection())
        second_map = {**SOURCE_MAP, "document_id": "doc_material_2"}
        second = material_facts_from_review(mission_id="mission_material", source_map=second_map, selection={**selection(), "document_id": "doc_material_2"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = write_material_facts_for_document(root, first)
            second_path = write_material_facts_for_document(root, second)
            items = iter_material_facts(root, "mission_material")
        self.assertNotEqual(first_path, second_path)
        self.assertEqual([item["document_id"] for item in items], ["doc_material", "doc_material_2"])

    def test_persisted_facts_must_still_match_the_current_source_map(self) -> None:
        artifact = material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=selection())
        validate_material_fact_source_links(
            mission_id="mission_material", artifacts=(artifact,), source_maps=(SOURCE_MAP,),
        )
        altered = {**artifact, "facts": [{**artifact["facts"][0], "source_quote_sha256": "b" * 64}, *artifact["facts"][1:]]}
        with self.assertRaisesRegex(MaterialExtractionError, "not linked"):
            validate_material_fact_source_links(
                mission_id="mission_material", artifacts=(altered,), source_maps=(SOURCE_MAP,),
            )
        with self.assertRaisesRegex(MaterialExtractionError, "current reviewed source map"):
            validate_material_fact_source_links(
                mission_id="mission_material", artifacts=(artifact,), source_maps=(),
            )

    def test_review_rejects_a_fact_not_linked_to_a_selected_segment(self) -> None:
        with self.assertRaises(MaterialExtractionError):
            material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=selection("unknown_segment"))

    def test_review_rejects_duplicate_ids_and_non_scalar_qualifiers(self) -> None:
        duplicate = selection()
        duplicate["facts"] = [duplicate["facts"][0], {**duplicate["facts"][1], "fact_id": "fact_comp"}]
        with self.assertRaisesRegex(MaterialExtractionError, "identity, category, or source segment"):
            material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=duplicate)
        nested_qualifier = selection()
        nested_qualifier["facts"] = [{**nested_qualifier["facts"][0], "qualifiers": {"conditions": {"temperature_k": 300}}}, *nested_qualifier["facts"][1:]]
        with self.assertRaisesRegex(MaterialExtractionError, "qualifier must be a scalar or null"):
            material_facts_from_review(mission_id="mission_material", source_map=SOURCE_MAP, selection=nested_qualifier)

    def test_prompt_is_scoped_to_selected_short_excerpts_and_not_a_conclusion(self) -> None:
        mission = MissionBrief("What is reported?", "BiFeO3", "phase stability", "films", mission_id="mission_material")
        system, user = material_extraction_prompts(mission, SOURCE_MAP)
        self.assertIn("untrusted JSON draft", system)
        self.assertIn("seg_1", user)
        self.assertIn(QUOTE, user)
        self.assertIn("experimental_condition", system)


if __name__ == "__main__":
    unittest.main()
