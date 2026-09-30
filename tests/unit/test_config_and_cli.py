from __future__ import annotations

from pathlib import Path

import pytest

from co_pipeline.cli import _selected_stages, build_parser
from co_pipeline.config import ConfigurationError, load_config


def _write_config(path: Path, *, profile: str = "reviewed") -> Path:
    path.write_text(
        f"""
profile: {profile}
paths:
  data_root: ${{CO_DATA_ROOT}}
  output_root: ${{CO_OUTPUT_ROOT}}
  cache_root: ${{CO_CACHE_ROOT}}
period:
  months: [8, 9, 10]
units:
  internal: mol/cm²
model:
  seed: 42
  ratio_clip: [0.2, 5.0]
validation:
  map_minimum_satellites: 2
  strong_agreement_satellites: 3
  neutral_z_threshold: 0.25
  regional_iqr_quantile: 0.33
regions:
  synthetic: {{longitude: [10.0, 11.0], latitude: [-1.0, 1.0]}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_config_expands_environment_and_has_stable_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("CO_DATA_ROOT", "CO_OUTPUT_ROOT", "CO_CACHE_ROOT"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    source = _write_config(tmp_path / "config.yaml")
    first = load_config(source)
    second = load_config(source)
    assert first.profile == "reviewed"
    assert first.fingerprint() == second.fingerprint()


def test_config_rejects_unknown_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CO_DATA_ROOT", "CO_OUTPUT_ROOT", "CO_CACHE_ROOT"):
        monkeypatch.setenv(name, str(tmp_path))
    with pytest.raises(ConfigurationError, match="profile"):
        load_config(_write_config(tmp_path / "config.yaml", profile="experimental"))


def test_cli_exposes_every_public_command() -> None:
    help_text = build_parser().format_help()
    assert "grid-iasi" in help_text
    assert "download-validation" in help_text
    assert "run" in help_text


def test_stage_selection_rejects_reverse_range() -> None:
    with pytest.raises(ValueError, match="must precede"):
        _selected_stages("validate", "grid-iasi")


def test_reviewed_profile_rejects_weakened_satellite_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("CO_DATA_ROOT", "CO_OUTPUT_ROOT", "CO_CACHE_ROOT"):
        monkeypatch.setenv(name, str(tmp_path))
    source = _write_config(tmp_path / "config.yaml")
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "map_minimum_satellites: 2", "map_minimum_satellites: 1"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="validation rules"):
        load_config(source)


def test_reviewed_profile_requires_regions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CO_DATA_ROOT", "CO_OUTPUT_ROOT", "CO_CACHE_ROOT"):
        monkeypatch.setenv(name, str(tmp_path))
    source = _write_config(tmp_path / "config.yaml")
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "regions:\n  synthetic: {longitude: [10.0, 11.0], latitude: [-1.0, 1.0]}\n",
            "regions: {}\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="at least one configured region"):
        load_config(source)
