import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.facilities import FacilityGateError, condition_differential, review_evidence, write_condition_matrix
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, Stance


def card(evidence_id: str, stance: Stance, **conditions: object) -> EvidenceCard:
    return EvidenceCard("claim", stance, "BiFeO3", "phase", conditions, "short located quote", Provenance("doc_" + evidence_id, "page:1", "fixture", access_policy=AccessPolicy.OA), evidence_id=evidence_id)


class FacilityTests(unittest.TestCase):
    def test_incomplete_conditions_are_rejected(self) -> None:
        review = review_evidence(card("e1", Stance.SUPPORT, sample_form="film"))
        self.assertEqual(review.status.value, "rejected")
        self.assertIn("strain_percent", review.missing_conditions)

    def test_blank_unknown_and_nonfinite_conditions_are_rejected(self) -> None:
        conditions = dict(sample_form=" film ", strain_percent=-2.0, substrate="unknown ", thickness_nm=float("nan"), temperature_k=300, method=" ")
        review = review_evidence(card("e1", Stance.SUPPORT, **conditions))
        self.assertEqual(review.status.value, "rejected")
        self.assertEqual(review.missing_conditions, ("substrate", "thickness_nm", "method"))

    def test_numeric_condition_representations_do_not_create_false_differences(self) -> None:
        support = card(
            "e_support",
            Stance.SUPPORT,
            sample_form="film",
            strain_percent=-2,
            substrate="LAO",
            thickness_nm=30,
            temperature_k=300,
            method="XRD",
        )
        contradict = card(
            "e_contradict",
            Stance.CONTRADICT,
            sample_form="film",
            strain_percent=-2.0,
            substrate="LAO",
            thickness_nm=30.0,
            temperature_k=300.0,
            method="XRD",
        )
        matrix = condition_differential((support, contradict), ("counterexample",))
        self.assertEqual(matrix.rows[0].differing_fields, ())

    def test_condition_matrix_artifact_omits_quotes(self) -> None:
        shared = dict(sample_form="film", substrate="LAO", thickness_nm=30, temperature_k=300, method="XRD")
        matrix = condition_differential(
            (card("e_support", Stance.SUPPORT, **shared, strain_percent=-2.0), card("e_contradict", Stance.CONTRADICT, **shared, strain_percent=-1.0)),
            ("counterexample",),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_condition_matrix(Path(directory), matrix)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["supporting_evidence_ids"], ["e_support"])
        self.assertNotIn("quote", json.dumps(payload))
    def test_diagnostics_requires_accepted_opposing_evidence_and_counterquery(self) -> None:
        shared = dict(sample_form="film", substrate="LAO", thickness_nm=30, temperature_k=300, method="XRD")
        support = card("e_support", Stance.SUPPORT, **shared, strain_percent=-2.0)
        contradict = card("e_contradict", Stance.CONTRADICT, **shared, strain_percent=-1.0)
        matrix = condition_differential((support, contradict), ("BiFeO3 thickness oxygen vacancy counterexample",))
        self.assertEqual(matrix.rows[0].supporting_evidence_ids, ("e_support",))
        self.assertIn("strain_percent", matrix.rows[0].differing_fields)
        with self.assertRaises(FacilityGateError):
            condition_differential((support, contradict), ())


if __name__ == "__main__":
    unittest.main()
