import unittest

from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import MissionBrief, ReviewStatus, StationType
from cosmatter.stations import StationGateError, StationRun, StationRunStatus


class StationRunTests(unittest.TestCase):
    def setUp(self) -> None:
        brief = MissionBrief(question="为什么有不同结论？", material="BiFeO3", property_name="phase", scope="thin films")
        self.run = StationRun(MissionDispatcher.from_project().assign(brief))

    def test_stations_cannot_be_skipped_and_release_requires_acceptance(self) -> None:
        with self.assertRaises(StationGateError):
            self.run.complete(StationType.RESEARCH_PLANNING, ("plan_1",))
        for station in (StationType.QUESTION_INTAKE, StationType.RESEARCH_PLANNING, StationType.SEARCH_SELECTION, StationType.EVIDENCE_EXTRACTION):
            self.run.complete(station, (f"artifact_{station.value}",))
        self.assertEqual(self.run.active_station, StationType.CROSS_CHECK_REVIEW)
        with self.assertRaises(StationGateError):
            self.run.complete(StationType.CROSS_CHECK_REVIEW, ("review_1",), ReviewStatus.UNREVIEWED)
        self.assertEqual(self.run.complete(StationType.CROSS_CHECK_REVIEW, ("review_1",), ReviewStatus.ACCEPTED), StationType.REPORT_DELIVERY)

    def test_release_gate_can_return_only_to_planning_with_a_reason(self) -> None:
        for station in (StationType.QUESTION_INTAKE, StationType.RESEARCH_PLANNING, StationType.SEARCH_SELECTION, StationType.EVIDENCE_EXTRACTION):
            self.run.complete(station, (f"artifact_{station.value}",))
        self.assertEqual(self.run.return_to_planning("need counterevidence coverage"), StationType.RESEARCH_PLANNING)
        self.assertEqual(self.run.statuses[StationType.CROSS_CHECK_REVIEW], StationRunStatus.WAITING)
        self.assertEqual(self.run.return_reason, "need counterevidence coverage")


if __name__ == "__main__":
    unittest.main()
