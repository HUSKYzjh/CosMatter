"""Publish a complete new run without replacing another research mission."""

from __future__ import annotations

import errno
import json
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory

from .audit import FlightRecorder, safe_run_id
from .models import FleetAssignment, MissionBrief, MissionState


class MissionRunConflict(ValueError):
    """The requested run name is already occupied."""


def write_new_mission(
    runs_dir: Path, run_id: str, brief: MissionBrief, assignment: FleetAssignment | None = None,
) -> Path:
    destination = runs_dir / safe_run_id(run_id)
    runs_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem. Readers discover the brief and its initial
    # events together, and a failed write leaves the requested run ID reusable.
    with TemporaryDirectory(dir=runs_dir, prefix=".create-mission-") as temporary:
        recorder = FlightRecorder(Path(temporary), run_id)
        (recorder.run_dir / "mission.json").write_text(
            json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        recorder.record(event_type="mission_created", actor="mission_control", state=MissionState.INTAKE, payload=brief.to_dict())
        if assignment is not None:
            (recorder.run_dir / "fleet_assignment.json").write_text(
                json.dumps(assignment.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            recorder.record(event_type="fleet_assigned", actor="mission_dispatch", state=MissionState.INTAKE, payload=assignment.to_dict())
        message = "run_id already exists; choose another identifier"
        released_empty_mode = None
        try:
            existing = destination.lstat()
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISDIR(existing.st_mode) or getattr(existing, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise MissionRunConflict(message)
            if os.name == "nt":
                # Windows cannot rename onto an existing empty directory. rmdir
                # atomically refuses a directory containing any existing artifacts.
                try:
                    destination.rmdir()
                    released_empty_mode = stat.S_IMODE(existing.st_mode)
                except FileNotFoundError:
                    pass  # A competing creator released the same empty directory.
                except OSError as error:
                    if error.errno in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise MissionRunConflict(message) from error
                    raise
            else:
                # POSIX rename can directly replace an empty directory.
                recorder.run_dir.chmod(stat.S_IMODE(existing.st_mode))
        try:
            recorder.run_dir.rename(destination)
            released_empty_mode = None
        except OSError as error:
            if error.errno in {errno.EEXIST, errno.ENOTEMPTY, errno.ENOTDIR, errno.EISDIR}:
                raise MissionRunConflict(message) from error
            raise
        finally:
            if released_empty_mode is not None:
                try:
                    destination.mkdir(mode=released_empty_mode)
                except FileExistsError:
                    pass  # Keep the result of a concurrent publication.
    return destination
