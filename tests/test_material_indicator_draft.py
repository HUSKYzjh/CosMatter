from __future__ import annotations

import hashlib
import json
import unittest

from cosmatter.deepseek import DraftCompletion
from cosmatter.material_indicator_draft import (
    DRAFT_TRUST_STATUS,
    MaterialIndicatorDraftError,
    combine_untrusted_indicator_value_drafts,
    indicator_value_draft_prompts,
    untrusted_indicator_value_draft,
)
from cosmatter.material_indicator_registry import QUALIFIER_FIELDS


QUOTE = "At room temperature the measured spontaneous polarization was approximately 60 uC/cm2 along [012]."


def shortlist() -> dict:
    return {
        "mission_id": "bfo-test",
        "catalog_id": "bfo-p0-experimental-indicators/v1",
        "material_scope": "BiFeO3",
        "trust_status": "private_unreviewed_local_indicator_shortlist_not_source_map_or_evidence",
        "documents": [
            {
                "document_id": "paper_a",
                "focus_indicator_ids": ["spontaneous_polarization_ps"],
                "segments": [
                    {
                        "segment_id": "seg_1",
                        "locator": "markdown_line:5-5",
                        "quote": QUOTE,
                        "quote_sha256": hashlib.sha256(QUOTE.encode()).hexdigest(),
                    }
                ],
            }
        ],
    }


def catalog() -> dict:
    return {
        "trust_status": "curated_indicator_vocabulary_not_scientific_evidence",
        "indicators": [
            {
                "indicator_id": "spontaneous_polarization_ps",
                "category": "property",
                "value_shape": "numeric",
                "allowed_reported_units": ["uC/cm2"],
                "required_qualifiers": ["sample_form", "orientation", "temperature", "field_protocol", "electrode", "measurement_geometry"],
            }
        ],
    }


def response(*, excerpt_index: int = 0, unit: str = "uC/cm2", facts: bool = True) -> str:
    return json.dumps(
        {
            "facts": ([
                {
                    "excerpt_index": excerpt_index,
                    "indicator_id": "spontaneous_polarization_ps",
                    "reported_value": 60,
                    "reported_lower": None,
                    "reported_upper": None,
                    "reported_uncertainty": None,
                    "reported_unit": unit,
                    "value_semantics": "approximate",
                    "measurement_method": "polarization measurement",
                    "qualifiers": [("room_temperature" if field == "temperature" else "not_checked") for field in QUALIFIER_FIELDS],
                    "limitation": "reported along [012]",
                }
            ] if facts else [])
        }
    )


class MaterialIndicatorDraftTests(unittest.TestCase):
    def test_prompts_are_bounded_and_contain_only_shortlisted_excerpt(self) -> None:
        system, user = indicator_value_draft_prompts(shortlist(), catalog())
        self.assertLess(len(system), 8_001)
        self.assertLess(len(user), 20_001)
        self.assertIn(QUOTE, user)
        self.assertIn("not_checked", system)
        self.assertIn("never quote a number", user)

    def test_valid_draft_is_quote_free_and_hash_bound(self) -> None:
        result = untrusted_indicator_value_draft(
            shortlist=shortlist(),
            catalog=catalog(),
            completion=DraftCompletion(content=response(), model="deepseek-v4-flash", request_id="request-secret"),
        )
        self.assertEqual(result["trust_status"], DRAFT_TRUST_STATUS)
        self.assertNotIn(QUOTE, json.dumps(result))
        self.assertNotIn("request-secret", json.dumps(result))
        fact = result["facts"][0]
        self.assertEqual(fact["source_quote_sha256"], hashlib.sha256(QUOTE.encode()).hexdigest())
        self.assertEqual(tuple(fact["qualifiers"]), QUALIFIER_FIELDS)
        self.assertEqual(fact["supporting_segment_bindings"], [])
        self.assertEqual(result["input_segment_bindings"][0]["segment_id"], "seg_1")

    def test_combines_validated_batches_and_rejects_duplicate_fact_ids(self) -> None:
        first = untrusted_indicator_value_draft(
            shortlist=shortlist(), catalog=catalog(),
            completion=DraftCompletion(content=response(), model="deepseek-v4-flash", request_id="request-1"),
        )
        second = json.loads(json.dumps(first))
        second["facts"][0]["draft_fact_id"] = "paper_a_ps_02"
        second["facts"][0]["segment_id"] = "seg_2"
        second["facts"][0]["locator"] = "markdown_line:7-7"
        second["input_segment_bindings"][0]["segment_id"] = "seg_2"
        combined = combine_untrusted_indicator_value_drafts([first, second])
        self.assertEqual(combined["provider_batch_count"], 2)
        self.assertEqual(len(combined["facts"]), 1)
        self.assertEqual(combined["duplicate_fact_count"], 1)
        self.assertEqual(combined["facts"][0]["supporting_segment_bindings"][0]["segment_id"], "seg_2")
        self.assertEqual(first["facts"][0]["supporting_segment_bindings"], [])
        with self.assertRaisesRegex(MaterialIndicatorDraftError, "duplicate"):
            combine_untrusted_indicator_value_drafts([first, first])

    def test_duplicate_prefers_fact_with_more_checked_qualifiers(self) -> None:
        first = untrusted_indicator_value_draft(
            shortlist=shortlist(), catalog=catalog(),
            completion=DraftCompletion(content=response(), model="deepseek-v4-flash", request_id="request-1"),
        )
        second = json.loads(json.dumps(first))
        second["facts"][0]["draft_fact_id"] = "paper_a_ps_more_grounded"
        second["facts"][0]["segment_id"] = "seg_2"
        second["facts"][0]["locator"] = "markdown_line:7-7"
        second["facts"][0]["source_quote_sha256"] = "b" * 64
        second["facts"][0]["qualifiers"]["orientation"] = "[012]"
        second["input_segment_bindings"][0] = {
            "document_id": "paper_a", "segment_id": "seg_2", "source_quote_sha256": "b" * 64,
        }
        combined = combine_untrusted_indicator_value_drafts([first, second])
        self.assertEqual(combined["facts"][0]["segment_id"], "seg_2")
        self.assertEqual(combined["facts"][0]["supporting_segment_bindings"][0]["segment_id"], "seg_1")

    def test_rejects_unbound_segment_and_non_catalog_unit(self) -> None:
        for content in (response(excerpt_index=1), response(unit="C/m2")):
            with self.assertRaises(MaterialIndicatorDraftError):
                untrusted_indicator_value_draft(
                    shortlist=shortlist(),
                    catalog=catalog(),
                    completion=DraftCompletion(content=content, model="deepseek-v4-flash", request_id=None),
                )

    def test_accepts_empty_fact_list_without_inventing_an_observation(self) -> None:
        result = untrusted_indicator_value_draft(
            shortlist=shortlist(), catalog=catalog(),
            completion=DraftCompletion(content=response(facts=False), model="deepseek-v4-flash", request_id=None),
        )
        self.assertEqual(result["facts"], [])
        self.assertEqual(len(result["input_segment_bindings"]), 1)

    def test_controlled_partial_mode_counts_and_drops_invalid_facts(self) -> None:
        invalid = json.loads(response(unit="C/m2"))["facts"][0]
        valid = json.loads(response())["facts"][0]
        result = untrusted_indicator_value_draft(
            shortlist=shortlist(), catalog=catalog(),
            completion=DraftCompletion(content=json.dumps({"facts": [invalid, valid]}), model="deepseek-v4-flash", request_id=None),
            drop_invalid_facts=True,
        )
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(result["rejected_fact_count"], 1)
        self.assertEqual(result["rejection_reason_counts"], {"unit_not_catalog_allowed": 1})

    def test_rejects_tampered_quote_hash(self) -> None:
        value = shortlist()
        value["documents"][0]["segments"][0]["quote_sha256"] = "0" * 64
        with self.assertRaisesRegex(MaterialIndicatorDraftError, "hash"):
            indicator_value_draft_prompts(value, catalog())

    def test_accepts_explanatory_prefix_around_one_complete_json_object(self) -> None:
        result = untrusted_indicator_value_draft(
            shortlist=shortlist(),
            catalog=catalog(),
            completion=DraftCompletion(
                content="Here is the requested JSON:\n```JSON\n" + response() + "\n```",
                model="deepseek-v4-flash",
                request_id=None,
            ),
        )
        self.assertEqual(len(result["facts"]), 1)


if __name__ == "__main__":
    unittest.main()
