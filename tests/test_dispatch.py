import unittest

from cosmatter.dispatch import DispatchError, MissionDispatcher
from cosmatter.models import FacilityType, FleetType, MissionBrief, ReviewStatus


def brief(question: str) -> MissionBrief:
    return MissionBrief(
        question=question,
        material="BiFeO3",
        property_name="phase stability",
        scope="epitaxial thin films",
    )


class DispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatcher = MissionDispatcher.from_project()

    def test_all_five_fleets_load_from_configuration(self) -> None:
        self.assertEqual(set(self.dispatcher.specs), set(FleetType))

    def test_discrepancy_question_routes_to_diagnostics_fleet(self) -> None:
        assignment = self.dispatcher.assign(brief("为什么两篇论文对 BiFeO3 应变相变给出不同结论？"))
        self.assertEqual(assignment.fleet_type, FleetType.ROUTE_DIAGNOSTICS)
        self.assertEqual(assignment.mission_type, "literature_discrepancy")
        self.assertIn(FacilityType.CONDITION_DIFFERENTIAL, assignment.required_facilities)

    def test_evidence_question_routes_to_patrol_fleet(self) -> None:
        assignment = self.dispatcher.assign(brief("哪篇论文的原文支持这个说法？"))
        self.assertEqual(assignment.fleet_type, FleetType.EVIDENCE_PATROL)
        self.assertEqual(assignment.mission_type, "claim_verification")

    def test_unknown_question_defaults_to_survey_fleet(self) -> None:
        assignment = self.dispatcher.assign(brief("请整理 BiFeO3 薄膜研究。"))
        self.assertEqual(assignment.fleet_type, FleetType.DEEP_SPACE_SURVEY)
        self.assertIn("default", assignment.reason)

    def test_handoff_requires_accepted_verification(self) -> None:
        assignment = self.dispatcher.assign(brief("两篇论文的结论为什么不同？"))
        with self.assertRaises(DispatchError):
            self.dispatcher.handoff(
                assignment,
                FleetType.MISSION_VALIDATION,
                ("matrix_001",),
                ReviewStatus.UNREVIEWED,
                "needs a discriminating validation design",
            )
        handoff = self.dispatcher.handoff(
            assignment,
            FleetType.MISSION_VALIDATION,
            ("matrix_001",),
            ReviewStatus.ACCEPTED,
            "needs a discriminating validation design",
        )
        self.assertEqual(handoff.to_fleet, FleetType.MISSION_VALIDATION)


if __name__ == "__main__":
    unittest.main()
