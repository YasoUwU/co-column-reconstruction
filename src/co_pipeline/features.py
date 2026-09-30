"""Feature and target transformations shared by training and inference."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .constants import REPORT_CORRECTION_BOUNDS

ABCD_FEATURE_NAMES = (
    "log_CO_source",
    "lat",
    "lon",
    "sin_lat",
    "sin_lon",
    "cos_lon",
    "sin_month",
    "cos_month",
    "sin_doy",
    "cos_doy",
    "frp_mean",
    "frp_total",
    "severity_score",
    "log1p_frp_total",
)
"""Canonical 14-feature ABCD model contract, in persisted model-column order."""


def log_ratio_target(
    observed: ArrayLike,
    source: ArrayLike,
    *,
    correction_bounds: tuple[float, float] = REPORT_CORRECTION_BOUNDS,
) -> NDArray[np.float64]:
    """Compute the report target: the clipped log of observed/source."""

    observation = np.asarray(observed, dtype=float)
    baseline = np.asarray(source, dtype=float)
    if observation.shape != baseline.shape:
        raise ValueError("observed and source arrays must have identical shapes")
    if np.any(~np.isfinite(observation)) or np.any(~np.isfinite(baseline)):
        raise ValueError("observed and source arrays must be finite")
    if np.any(observation <= 0) or np.any(baseline <= 0):
        raise ValueError("log-ratio inputs must be strictly positive")
    lower, upper = correction_bounds
    if not (0 < lower <= upper and np.isfinite(lower) and np.isfinite(upper)):
        raise ValueError("correction bounds must be finite, positive, and ordered")
    return np.log(np.clip(observation / baseline, lower, upper))


def reconstruct_positive_column(
    source: ArrayLike,
    predicted_log_ratio: ArrayLike,
    *,
    correction_bounds: tuple[float, float] = REPORT_CORRECTION_BOUNDS,
) -> NDArray[np.float64]:
    """Apply a clipped multiplicative correction while preserving positivity."""

    baseline = np.asarray(source, dtype=float)
    prediction = np.asarray(predicted_log_ratio, dtype=float)
    if baseline.shape != prediction.shape:
        raise ValueError("source and predicted_log_ratio must have identical shapes")
    lower, upper = correction_bounds
    if not (0 < lower <= upper and np.isfinite(lower) and np.isfinite(upper)):
        raise ValueError("correction bounds must be finite, positive, and ordered")
    if np.any(~np.isfinite(baseline)) or np.any(baseline <= 0):
        raise ValueError("source values must be finite and strictly positive")
    if np.any(~np.isfinite(prediction)):
        raise ValueError("predicted log-ratios must be finite")
    factor = np.clip(np.exp(prediction), lower, upper)
    return baseline * factor


@dataclass(frozen=True)
class TemporalSplit:
    train: NDArray[np.bool_]
    evaluation: NDArray[np.bool_]


def temporal_split(
    years: ArrayLike,
    *,
    train_start: int,
    train_end: int,
    evaluation_start: int,
    evaluation_end: int,
) -> TemporalSplit:
    """Create disjoint inclusive year masks and reject temporal leakage."""

    if train_start > train_end or evaluation_start > evaluation_end:
        raise ValueError("Each year interval must be ordered")
    if train_end >= evaluation_start:
        raise ValueError("Training must end before evaluation begins")
    values = np.asarray(years)
    train = (values >= train_start) & (values <= train_end)
    evaluation = (values >= evaluation_start) & (values <= evaluation_end)
    if np.any(train & evaluation):
        raise AssertionError("Temporal split leaked observations across partitions")
    return TemporalSplit(train=train, evaluation=evaluation)


def broadcast_monthly_domain_feature(
    monthly_values: ArrayLike, month_index: ArrayLike
) -> NDArray[np.float64]:
    """Broadcast a domain-level monthly covariate to individual observations."""

    monthly = np.asarray(monthly_values, dtype=float)
    indices = np.asarray(month_index, dtype=int)
    if monthly.ndim != 1:
        raise ValueError("monthly_values must be one-dimensional")
    if np.any(indices < 0) or np.any(indices >= monthly.size):
        raise ValueError("month_index contains an out-of-range month")
    return monthly[indices]


def _parse_date(value: date | datetime | str | np.datetime64) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, np.datetime64):
        return date.fromisoformat(str(value.astype("datetime64[D]")))
    compact = value.strip()
    try:
        return datetime.strptime(compact, "%Y%m%d").date()
    except ValueError:
        return date.fromisoformat(compact)


def build_abcd_features(
    source: ArrayLike,
    latitude: ArrayLike,
    longitude: ArrayLike,
    observation_date: date | datetime | str | np.datetime64,
    *,
    frp_mean: float,
    frp_total: float,
    severity_score: float,
    mask: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Build the report's canonical ABCD features in fixed model-column order.

    The three FRP statistics are domain-level monthly values, intentionally
    broadcast across the daily spatial grid to reproduce the report workflow.
    """

    source_array = np.asarray(source, dtype=float)
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    if source_array.ndim != 2 or lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("source must be 2-D and latitude/longitude must be 1-D")
    if source_array.shape != (lat.size, lon.size):
        raise ValueError("source shape must equal (latitude.size, longitude.size)")
    if np.any(~np.isfinite(source_array)) or np.any(source_array <= 0):
        raise ValueError("source values must be finite and strictly positive")
    frp = np.asarray([frp_mean, frp_total, severity_score], dtype=float)
    if np.any(~np.isfinite(frp)):
        raise ValueError("FRP features must be finite")
    parsed_date = _parse_date(observation_date)
    day_of_year = parsed_date.timetuple().tm_yday
    lon_2d, lat_2d = np.meshgrid(lon, lat)
    sample_count = source_array.size
    month_angle = 2.0 * np.pi * parsed_date.month / 12.0
    day_angle = 2.0 * np.pi * day_of_year / 366.0
    columns = (
        np.log(source_array.ravel()),
        lat_2d.ravel(),
        lon_2d.ravel(),
        np.sin(np.deg2rad(lat_2d.ravel())),
        np.sin(np.deg2rad(lon_2d.ravel())),
        np.cos(np.deg2rad(lon_2d.ravel())),
        np.full(sample_count, np.sin(month_angle)),
        np.full(sample_count, np.cos(month_angle)),
        np.full(sample_count, np.sin(day_angle)),
        np.full(sample_count, np.cos(day_angle)),
        np.full(sample_count, frp_mean),
        np.full(sample_count, frp_total),
        np.full(sample_count, severity_score),
        np.full(sample_count, np.log1p(max(frp_total, 0.0))),
    )
    features = np.column_stack(columns)
    if mask is None:
        return features
    selection = np.asarray(mask, dtype=bool)
    if selection.shape != source_array.shape:
        raise ValueError("mask shape must match source shape")
    return features[selection.ravel()]
