from __future__ import annotations

from pathlib import Path

import pytest

from co_pipeline.config import PipelineConfig
from co_pipeline.io import DataContractError
from co_pipeline.stages import _expected_product_dates, _validate_product_coverage


def _config(tmp_path: Path, *, enforce: bool = True) -> PipelineConfig:
    expected = {"20230801", "20230802", "20230901"}
    return PipelineConfig(
        source=tmp_path / "config.yaml",
        values={
            "profile": "reviewed",
            "period": {"product_years": [2023, 2023], "months": [8, 9]},
            "coverage": {
                "enforce_complete": enforce,
                "expected_product_days": 60,
                "allowed_missing_dates": [],
            },
            "test_expected_subset": expected,
        },
    )


def test_expected_dates_use_real_calendar_month_lengths(tmp_path: Path) -> None:
    dates = _expected_product_dates(_config(tmp_path))
    assert len(dates) == 61
    assert "20230831" in dates
    assert "20230930" in dates


def test_coverage_rejects_undeclared_missing_day(tmp_path: Path) -> None:
    config = _config(tmp_path)
    paths = [tmp_path / f"common_grid_{day}.nc" for day in _expected_product_dates(config)]
    paths.pop()
    with pytest.raises(DataContractError, match="coverage mismatch"):
        _validate_product_coverage(config, paths)


def test_coverage_can_be_disabled_for_synthetic_examples(tmp_path: Path) -> None:
    _validate_product_coverage(
        _config(tmp_path, enforce=False), [tmp_path / "common_grid_20230801.nc"]
    )
