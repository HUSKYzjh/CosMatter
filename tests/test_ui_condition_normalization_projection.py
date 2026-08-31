import unittest

from cosmatter.ui_export import _condition_normalization_projection


class UiConditionNormalizationProjectionTests(unittest.TestCase):
    def test_projects_only_reviewer_declared_names_and_units(self) -> None:
        projected = _condition_normalization_projection({
            "trust_status": "human_reviewed_condition_normalization_no_conversion",
            "mappings": [{"evidence_id": "e1", "raw_field": "thickness_nm", "canonical_field": "thickness", "unit": "nm"}],
        })
        self.assertEqual(projected, {
            "trust_status": "human_reviewed_condition_normalization_no_conversion",
            "mappings": [{"evidence_id": "e1", "raw_field": "thickness_nm", "canonical_field": "thickness", "unit": "nm"}],
        })
