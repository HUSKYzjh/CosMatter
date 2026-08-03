"""Strict, dependency-free loading for CosMatter fleet configuration files."""

from __future__ import annotations

from pathlib import Path

from .models import FacilityType, FleetSpec, FleetType, StationType


class FleetConfigError(ValueError):
    """Raised when a fleet YAML file violates the intentionally small schema."""


_LIST_FIELDS = {
    "mission_types",
    "required_stations",
    "required_facilities",
    "handoff_allowed_to",
}
_SCALAR_FIELDS = {"fleet_id", "release_gate", "max_planning_loops", "max_facility_attempts"}


def _parse_scalar(value: str) -> str | int:
    return int(value) if value.isdigit() else value


def load_fleet_spec(path: Path) -> FleetSpec:
    """Load one restricted YAML mapping without accepting arbitrary YAML features."""
    raw: dict[str, object] = {field: [] for field in _LIST_FIELDS}
    display_name: dict[str, str] = {}
    active_block: str | None = None

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not line:
            continue
        indentation = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indentation == 0:
            if ":" not in text:
                raise FleetConfigError(f"{path}:{line_number}: expected key:value")
            key, value = (part.strip() for part in text.split(":", maxsplit=1))
            if key == "display_name" and not value:
                active_block = key
                continue
            if key in _LIST_FIELDS and not value:
                active_block = key
                continue
            if key not in _SCALAR_FIELDS:
                raise FleetConfigError(f"{path}:{line_number}: unknown field {key!r}")
            raw[key] = _parse_scalar(value)
            active_block = None
        elif indentation == 2 and active_block in _LIST_FIELDS and text.startswith("- "):
            cast_list = raw[active_block]
            assert isinstance(cast_list, list)
            cast_list.append(text[2:].strip())
        elif indentation == 2 and active_block == "display_name" and ":" in text:
            key, value = (part.strip() for part in text.split(":", maxsplit=1))
            if key not in {"zh", "en"} or not value:
                raise FleetConfigError(f"{path}:{line_number}: display_name requires nonempty zh/en")
            display_name[key] = value
        else:
            raise FleetConfigError(f"{path}:{line_number}: unsupported indentation or YAML feature")

    required = _SCALAR_FIELDS | {"display_name"}
    missing = [field for field in required if field != "display_name" and field not in raw]
    if missing or set(display_name) != {"zh", "en"}:
        raise FleetConfigError(f"{path}: missing fields: {', '.join(sorted(missing + ([] if set(display_name) == {'zh', 'en'} else ['display_name.zh/en'])))}")
    for field in _LIST_FIELDS:
        if not raw[field]:
            raise FleetConfigError(f"{path}: {field} must not be empty")

    try:
        return FleetSpec(
            fleet_type=FleetType(str(raw["fleet_id"])),
            display_name_zh=display_name["zh"],
            display_name_en=display_name["en"],
            mission_types=tuple(str(item) for item in raw["mission_types"]),
            required_stations=tuple(StationType(str(item)) for item in raw["required_stations"]),
            required_facilities=tuple(FacilityType(str(item)) for item in raw["required_facilities"]),
            handoff_allowed_to=tuple(FleetType(str(item)) for item in raw["handoff_allowed_to"]),
            release_gate=StationType(str(raw["release_gate"])),
            max_planning_loops=int(raw["max_planning_loops"]),
            max_facility_attempts=int(raw["max_facility_attempts"]),
        )
    except (TypeError, ValueError) as error:
        raise FleetConfigError(f"{path}: invalid fleet configuration: {error}") from error


def load_fleet_specs(config_dir: Path) -> dict[FleetType, FleetSpec]:
    """Load a unique spec for every fleet configuration in a directory."""
    specs: dict[FleetType, FleetSpec] = {}
    for path in sorted(config_dir.glob("*.yaml")):
        spec = load_fleet_spec(path)
        if spec.fleet_type in specs:
            raise FleetConfigError(f"duplicate fleet_id {spec.fleet_type.value!r}")
        specs[spec.fleet_type] = spec
    if not specs:
        raise FleetConfigError(f"no fleet configuration files found in {config_dir}")
    return specs
