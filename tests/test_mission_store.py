from __future__ import annotations

import errno
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch

from cosmatter.audit import FlightRecorder
from cosmatter.cli import main
from cosmatter.local_api import LocalApiError, LocalMissionApi


class MissionCreationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runs = Path(temp.name) / "runs"
        self.api = LocalMissionApi(self.runs)
        self.brief = dict(question='How does sample "A"\nrespond?', material="film A", property="strain", scope="0–2%\ncoherent films", run_id="shared")
        self.run = self.runs / "shared"
        self.run.mkdir(parents=True)
        self.enterContext(patch("cosmatter.cli._runs_dir", return_value=self.runs))
        self.enterContext(patch("cosmatter.cli._json_print"))

    def cli_create(self):
        return main(["create-mission", "--run-id", "shared", "--mission-id", "mission_cli_fixture",
                     "--question", "Which phases occur?", "--material", "film B", "--property", "symmetry", "--scope", "10 K"])

    def test_cli_and_api_refuse_to_overwrite_an_existing_brief(self):
        self.api.create_mission(self.brief)
        before = {p.name: p.read_bytes() for p in self.run.iterdir()}
        self.assertEqual(self.cli_create(), 2)
        with self.assertRaises(LocalApiError) as conflict:
            self.api.create_mission(self.brief)
        self.assertEqual(conflict.exception.status, 409)
        self.assertEqual({p.name: p.read_bytes() for p in self.run.iterdir()}, before)

    def test_racing_cli_and_api_publish_one_complete_consistent_run(self):
        gate = Barrier(2)
        record = FlightRecorder.record

        def concurrent_record(recorder, **event):
            if event["event_type"] == "mission_created":
                gate.wait(timeout=10)
            return record(recorder, **event)

        with patch.object(FlightRecorder, "record", new=concurrent_record), ThreadPoolExecutor(2) as workers:
            cli = workers.submit(self.cli_create)
            api = workers.submit(self.api.create_mission, self.brief)
            cli_won = cli.result() == 0
            if cli_won:
                with self.assertRaises(LocalApiError) as conflict:
                    api.result()
                self.assertEqual(conflict.exception.status, 409)
            else:
                self.assertEqual(api.result()["run_id"], "shared")

        mission = json.loads((self.run / "mission.json").read_text("utf-8"))
        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text("utf-8").splitlines()]
        self.assertEqual(events[0]["payload"], mission)
        self.assertEqual(mission["material"], "film B" if cli_won else self.brief["material"])
        expected_events = ["mission_created"] if cli_won else ["mission_created", "fleet_assigned"]
        self.assertEqual([event["event_type"] for event in events], expected_events)
        self.assertEqual((self.run / "fleet_assignment.json").is_file(), not cli_won)
        if not cli_won:
            self.assertEqual(events[1]["payload"]["mission_id"], mission["mission_id"])
        self.assertEqual(list(self.runs.iterdir()), [self.run])

    def test_failed_staged_write_allows_retry_into_precreated_empty_directory(self):
        record = FlightRecorder.record

        def fail_assignment(recorder, **event):
            if event["event_type"] == "fleet_assigned":
                raise OSError("test event write interrupted")
            return record(recorder, **event)

        with patch.object(FlightRecorder, "record", new=fail_assignment), self.assertRaisesRegex(OSError, "interrupted"):
            self.api.create_mission(self.brief)
        self.assertEqual(list(self.run.iterdir()), [])
        self.assertEqual(list(self.runs.iterdir()), [self.run])
        self.assertEqual(self.cli_create(), 0)

    def test_failed_publication_preserves_precreated_empty_directory_for_retry(self):
        for error in (PermissionError(errno.EACCES, "fixture publication error"), KeyboardInterrupt()):
            with self.subTest(failure=type(error).__name__), patch.object(Path, "rename", side_effect=error):
                with self.assertRaises(type(error)):
                    self.api.create_mission(self.brief)
                self.assertEqual(list(self.run.iterdir()), [])
                self.assertEqual(list(self.runs.iterdir()), [self.run])
        self.assertEqual(self.api.create_mission(self.brief)["run_id"], "shared")

    def test_prior_directory_contents_survive_both_creation_entry_points(self):
        note = self.run / "review" / "notes.txt"
        note.parent.mkdir()
        note.write_bytes(b"preserve researcher notes")
        self.assertEqual(self.cli_create(), 2)
        with self.assertRaises(LocalApiError) as conflict:
            self.api.create_mission(self.brief)
        self.assertEqual(conflict.exception.status, 409)
        self.assertEqual(list(self.run.iterdir()), [note.parent])
        self.assertEqual(note.read_bytes(), b"preserve researcher notes")

    def test_readers_see_the_mission_only_after_both_initial_events_are_ready(self):
        staged, release = Event(), Event()
        record = FlightRecorder.record

        def pause_before_last_event(recorder, **event):
            if event["event_type"] == "fleet_assigned":
                staged.set()
                if not release.wait(timeout=10):
                    raise TimeoutError("fixture reader did not release the writer")
            return record(recorder, **event)

        with patch.object(FlightRecorder, "record", new=pause_before_last_event), ThreadPoolExecutor(1) as pool:
            writer = pool.submit(self.api.create_mission, self.brief)
            try:
                self.assertTrue(staged.wait(timeout=10))
                self.assertEqual(self.api.recent_runs()["runs"], [])
                with self.assertRaises(LocalApiError) as unavailable:
                    self.api.run_status("shared")
                self.assertEqual(unavailable.exception.status, 404)
                self.assertEqual(list(self.run.iterdir()), [])
            finally:
                release.set()
            mission = writer.result()

        self.assertEqual([run["run_id"] for run in self.api.recent_runs()["runs"]], ["shared"])
        self.assertEqual(self.api.run_status("shared")["mission_id"], mission["mission_id"])
        events = [json.loads(line)["event_type"] for line in (self.run / "events.jsonl").read_text("utf-8").splitlines()]
        self.assertEqual(events, ["mission_created", "fleet_assigned"])
