import unittest

from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, MissionState, Provenance, Stance
from cosmatter.state_machine import InvalidTransitionError, MissionMachine


class ModelAndStateTests(unittest.TestCase):
    def test_mission_rejects_missing_scope(self) -> None:
        with self.assertRaises(ValueError):
            MissionBrief(question="q", material="BiFeO3", property_name="phase", scope=" ")

    def test_evidence_requires_source_location(self) -> None:
        with self.assertRaises(ValueError):
            Provenance(document_id="doc-1", locator="", source="sciverse")

    def test_evidence_card_is_json_ready(self) -> None:
        card = EvidenceCard(
            claim="A T-like phase was reported under compressive strain.",
            stance=Stance.SUPPORT,
            material="BiFeO3",
            property_name="T-like phase stability",
            conditions={"sample_form": "epitaxial thin film", "strain_percent": None},
            quote="The film exhibits a tetragonal-like phase.",
            provenance=Provenance(
                document_id="doc-1",
                locator="paragraph:42",
                source="sciverse",
                access_policy=AccessPolicy.AUTHORIZED,
            ),
        )
        self.assertEqual(card.to_dict()["provenance"]["locator"], "paragraph:42")
        self.assertEqual(card.to_dict()["stance"], "support")

    def test_state_machine_rejects_a_report_before_verification(self) -> None:
        machine = MissionMachine()
        with self.assertRaises(InvalidTransitionError):
            machine.transition(MissionState.REPORT)

    def test_state_machine_completes_happy_path(self) -> None:
        machine = MissionMachine()
        for state in (
            MissionState.PLAN,
            MissionState.RETRIEVE,
            MissionState.SELECT,
            MissionState.EXTRACT,
            MissionState.MAP,
            MissionState.HAZARD_SCAN,
            MissionState.VERIFY,
            MissionState.REPORT,
            MissionState.COMPLETE,
        ):
            machine.transition(state)
        self.assertEqual(machine.state, MissionState.COMPLETE)
