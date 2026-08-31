"""Probe isolated DSH package combinations and minimise a failing set.

Every probe uses a new temporary DSH_HOME, local bundle paths, CI/noninteractive
mode, and ``dsh --dump-config`` only.  It never reads .env, starts a provider,
opens a run directory, or writes a user profile.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cosmatter.dsh_combination_lab import DshCombinationLabError, all_pairs, compact_report, minimise_failing_combination, normalize_package_selection


class ProbeError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", help="comma-separated package names; defaults to all seven")
    parser.add_argument("--all-pairs", action="store_true", help="probe every pair independently instead of one selected combination")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout_seconds <= 180:
        raise ProbeError("timeout must be between 5 and 180 seconds")
    group = _load_group()
    available = tuple(item["package"] for item in group["packages"])
    requested = tuple(args.packages.split(",")) if args.packages else available
    selected = normalize_package_selection(available, requested)
    probe_count = 0

    def probe(combo: tuple[str, ...]) -> bool:
        nonlocal probe_count
        probe_count += 1
        return _probe_combo(group, combo, args.timeout_seconds)

    if args.all_pairs:
        reports = []
        for pair in all_pairs(selected):
            healthy = probe(pair)
            minimal = minimise_failing_combination(pair, probe) if not healthy else None
            reports.append(compact_report(selected=pair, healthy=healthy, minimal_failure=minimal, probe_count=probe_count))
        print(json.dumps({"schema_version": "1.0", "trust_status": "isolated_dsh_combination_diagnostic_not_provider_execution_or_scientific_evidence", "pair_count": len(reports), "reports": reports}, ensure_ascii=False))
        return 0 if all(item["healthy"] for item in reports) else 2
    healthy = probe(selected)
    minimal = minimise_failing_combination(selected, probe) if not healthy else None
    print(json.dumps(compact_report(selected=selected, healthy=healthy, minimal_failure=minimal, probe_count=probe_count), ensure_ascii=False))
    return 0 if healthy else 2


def _probe_combo(group: dict[str, object], combo: tuple[str, ...], timeout: int) -> bool:
    dsh = shutil.which("dsh")
    if not dsh:
        raise ProbeError("dsh must be on PATH")
    entries = [item for item in group["packages"] if item["package"] in combo]
    with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-combination-") as directory:
        temp = Path(directory)
        environment = {**os.environ, "DSH_HOME": str(temp / "home"), "PYTHONPATH": "", "CI": "1"}
        paths = [str(ROOT / "plugins" / item["path"]) for item in entries]
        install = _run([dsh, "plugin", "--profile", "probe", "add", *paths], environment, timeout)
        if install.returncode:
            return False
        dump = _run([dsh, "--profile", "probe", "--dump-config"], environment, timeout)
        if dump.returncode:
            return False
        return all(f"id: {item['plugin_id']}" in dump.stdout for item in entries)


def _run(command: list[str], environment: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=ROOT, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise ProbeError("isolated DSH combination probe timed out") from error


def _load_group() -> dict[str, object]:
    try:
        payload = json.loads((ROOT / "plugins" / "dsh-plugin-group.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProbeError("DSH group manifest cannot be read") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("packages"), list) or not all(isinstance(item, dict) and isinstance(item.get("package"), str) and isinstance(item.get("path"), str) and isinstance(item.get("plugin_id"), str) for item in payload["packages"]):
        raise ProbeError("DSH group manifest is invalid")
    return payload


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, DshCombinationLabError) as error:
        print(json.dumps({"healthy": False, "error": str(error)}, ensure_ascii=False))
        raise SystemExit(2)
