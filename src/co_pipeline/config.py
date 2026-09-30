"""Configuration loading and validation for the public pipeline interface."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .constants import SUPPORTED_CO_UNITS

SUPPORTED_PROFILES = {"report-reproduction", "reviewed"}
_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


class ConfigurationError(ValueError):
    """Raised when a configuration cannot be used safely."""


def _expand_environment(value: Any) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigurationError(f"Required environment variable is not set: {name}")
            return os.environ[name]

        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class PipelineConfig:
    """Validated configuration with stable serialization and path resolution."""

    source: Path
    values: Mapping[str, Any]

    @property
    def profile(self) -> str:
        return str(self.values["profile"])

    def section(self, name: str) -> Mapping[str, Any]:
        value = self.values.get(name, {})
        if not isinstance(value, Mapping):
            raise ConfigurationError(f"Configuration section '{name}' must be a mapping")
        return value

    def value(self, dotted_key: str, default: Any = None) -> Any:
        """Read a nested value using a dotted key."""

        current: Any = self.values
        for part in dotted_key.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return default
            current = current[part]
        return current

    def path(self, section: str, key: str, *, create: bool = False) -> Path:
        raw = self.section(section).get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise ConfigurationError(f"Missing path: {section}.{key}")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (self.source.parent / candidate).resolve()
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    def rooted_path(self, root_key: str, relative: str | Path, *, create: bool = False) -> Path:
        """Resolve a path below one of the configured roots and prevent traversal."""

        root = self.path("paths", root_key, create=create).resolve()
        candidate = (root / Path(relative)).resolve()
        if candidate != root and root not in candidate.parents:
            raise ConfigurationError(f"Path escapes configured {root_key}: {relative}")
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    def normalized(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.values, sort_keys=True))

    def fingerprint(self) -> str:
        payload = json.dumps(self.normalized(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_config(path: str | Path) -> PipelineConfig:
    """Load YAML, expand explicit environment references, and validate invariants."""

    source = Path(path).resolve()
    if not source.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {source}")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError("The configuration root must be a mapping")
    values = _expand_environment(raw)
    profile = values.get("profile")
    if profile not in SUPPORTED_PROFILES:
        raise ConfigurationError(
            f"profile must be one of {sorted(SUPPORTED_PROFILES)}, got {profile!r}"
        )
    _validate_science(values)
    return PipelineConfig(source=source, values=values)


def _validate_science(values: Mapping[str, Any]) -> None:
    period = values.get("period")
    if not isinstance(period, Mapping):
        raise ConfigurationError("period must be a mapping")
    months = list(period.get("months", []))
    if months != [8, 9, 10]:
        raise ConfigurationError("The canonical ASO pipeline requires months [8, 9, 10]")
    model = values.get("model")
    if not isinstance(model, Mapping):
        raise ConfigurationError("model must be a mapping")
    if int(model.get("seed", -1)) != 42:
        raise ConfigurationError("The canonical reproducibility seed is 42")
    clipping = list(model.get("ratio_clip", []))
    if clipping != [0.2, 5.0]:
        raise ConfigurationError("model.ratio_clip must be [0.2, 5.0]")
    units = values.get("units")
    if not isinstance(units, Mapping) or units.get("internal") != "mol/cm²":
        raise ConfigurationError("The canonical internal unit is mol/cm²")
    source_units = values.get("source_units", {})
    if not isinstance(source_units, Mapping):
        raise ConfigurationError("source_units must be a mapping")
    unsupported = {
        key: unit for key, unit in source_units.items() if unit not in SUPPORTED_CO_UNITS
    }
    if unsupported:
        raise ConfigurationError(
            f"Unsupported source_units entries: {unsupported}; "
            f"allowed values are {sorted(SUPPORTED_CO_UNITS)}"
        )
    profile = str(values["profile"])
    validation = values.get("validation", {})
    if not isinstance(validation, Mapping):
        raise ConfigurationError("validation must be a mapping")
    if profile == "reviewed":
        required = {
            "map_minimum_satellites": 2,
            "strong_agreement_satellites": 3,
            "neutral_z_threshold": 0.25,
            "regional_iqr_quantile": 0.33,
        }
        mismatches = {
            key: validation.get(key)
            for key, expected in required.items()
            if validation.get(key) != expected
        }
        if mismatches:
            raise ConfigurationError(
                f"reviewed profile validation rules were changed: {mismatches}"
            )
        regions = values.get("regions")
        if not isinstance(regions, Mapping) or not regions:
            raise ConfigurationError("reviewed profile requires at least one configured region")
        for name, bounds in regions.items():
            if not isinstance(bounds, Mapping) or set(bounds) != {"longitude", "latitude"}:
                raise ConfigurationError(
                    f"region {name!r} must define longitude and latitude bounds"
                )
            for coordinate in ("longitude", "latitude"):
                limits = bounds[coordinate]
                if (
                    not isinstance(limits, list)
                    or len(limits) != 2
                    or float(limits[0]) >= float(limits[1])
                ):
                    raise ConfigurationError(f"region {name!r} has invalid {coordinate} bounds")
