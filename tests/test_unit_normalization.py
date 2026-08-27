import unittest

from cosmatter.material_extraction import MaterialExtractionError, material_facts_from_review
from cosmatter.unit_normalization import UnitNormalizationError, validate_reported_normalization

from test_material_extraction import SOURCE_MAP, selection


class UnitNormalizationTests(unittest.TestCase):
    def test_supported_materials_units_validate_exact_conversion(self) -> None:
        validate_reported_normalization(30, "nm", 3e-8, "m")
        validate_reported_normalization(3, "µC/cm²", 0.03, "C/m²")
        validate_reported_normalization(300, "K", 26.85, "°C")
        validate_reported_normalization(1, "GPa", 1000, "MPa")

    def test_common_materials_unicode_and_condition_units_are_checked(self) -> None:
        micro, degree, angstrom = chr(181), chr(176), chr(197)
        validate_reported_normalization(2, micro + "m", 2e-6, "m")
        validate_reported_normalization(5, angstrom, 0.5, "nm")
        validate_reported_normalization(300, "K", 26.85, degree + "C")
        validate_reported_normalization(1, "%", 0.01, "fraction")
        validate_reported_normalization(1, "emu/cm3", 1000, "A/m")
        validate_reported_normalization(2, "GHz", 2e9, "Hz")
        validate_reported_normalization(5, "g/cm3", 5000, "kg/m3")

    def test_mismatched_known_units_or_values_are_rejected(self) -> None:
        with self.assertRaises(UnitNormalizationError):
            validate_reported_normalization(3, "µC/cm2", 3, "C/m2")
        with self.assertRaises(UnitNormalizationError):
            validate_reported_normalization(10, "nm", 10, "K")

    def test_reviewed_material_fact_rejects_inconsistent_conversion(self) -> None:
        reviewed = selection()
        reviewed["facts"][1]["unit"] = "K"
        reviewed["facts"][1]["normalized_value"] = 200
        reviewed["facts"][1]["normalized_unit"] = "K"
        with self.assertRaises(MaterialExtractionError):
            material_facts_from_review(
                mission_id="mission_material", source_map=SOURCE_MAP, selection=reviewed,
            )

    def test_unknown_units_remain_reviewable_without_guessed_conversion(self) -> None:
        validate_reported_normalization(1, "arbitrary unit", 17, "another arbitrary unit")


if __name__ == "__main__":
    unittest.main()
