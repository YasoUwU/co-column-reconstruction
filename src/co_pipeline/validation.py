"""Satellite-consensus and robust regional validation utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class ConsensusResult:
    median: NDArray[np.float64]
    count: NDArray[np.int64]
    direction: NDArray[np.int8]
    strong_agreement: NDArray[np.bool_]


def satellite_median(
    anomalies: ArrayLike, *, satellite_axis: int = 0, minimum_satellites: int = 2
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Calculate a median only where the requested satellite coverage is met."""

    if minimum_satellites < 1:
        raise ValueError("minimum_satellites must be at least one")
    values = np.asarray(anomalies, dtype=float)
    axis = satellite_axis + values.ndim if satellite_axis < 0 else satellite_axis
    if not 0 <= axis < values.ndim:
        raise ValueError(
            f"satellite_axis {satellite_axis} is out of bounds for {values.ndim} dimensions"
        )
    count = np.sum(np.isfinite(values), axis=axis)
    with np.errstate(all="ignore"):
        median = np.nanmedian(values, axis=axis)
    median = np.where(count >= minimum_satellites, median, np.nan)
    return median, count


def satellite_consensus(
    anomalies: ArrayLike,
    *,
    satellite_axis: int = 0,
    minimum_satellites: int = 2,
    strong_satellites: int = 3,
    neutral_tolerance: float = 0.25,
) -> ConsensusResult:
    """Classify the sign and strong cross-satellite agreement of anomalies.

    Direction is -1, 0, or +1 according to the median and neutral tolerance.
    Strong agreement requires at least ``strong_satellites`` finite values, all of
    whose classified signs match the non-neutral median direction.
    """

    if strong_satellites < minimum_satellites:
        raise ValueError("strong_satellites cannot be smaller than minimum_satellites")
    if not np.isfinite(neutral_tolerance) or neutral_tolerance < 0:
        raise ValueError("neutral_tolerance must be finite and non-negative")
    values = np.asarray(anomalies, dtype=float)
    axis = satellite_axis + values.ndim if satellite_axis < 0 else satellite_axis
    if not 0 <= axis < values.ndim:
        raise ValueError(
            f"satellite_axis {satellite_axis} is out of bounds for {values.ndim} dimensions"
        )
    median, count = satellite_median(
        values, satellite_axis=axis, minimum_satellites=minimum_satellites
    )
    direction = np.where(
        np.isnan(median),
        0,
        np.where(
            median >= neutral_tolerance,
            1,
            np.where(median <= -neutral_tolerance, -1, 0),
        ),
    ).astype(np.int8)
    signs = np.where(
        ~np.isfinite(values),
        0,
        np.where(
            values >= neutral_tolerance,
            1,
            np.where(values <= -neutral_tolerance, -1, 0),
        ),
    )
    expanded_direction = np.expand_dims(direction, axis=axis)
    finite = np.isfinite(values)
    all_match = np.all(~finite | (signs == expanded_direction), axis=axis)
    strong = (count >= strong_satellites) & (direction != 0) & all_match
    return ConsensusResult(median, count, direction, strong)


def regional_iqr_threshold(values: ArrayLike, *, quantile: float = 1 / 3) -> float:
    """Return the selected quantile of finite regional IQR values."""

    if not 0 <= quantile <= 1:
        raise ValueError("quantile must lie in [0, 1]")
    array = np.asarray(values, dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        raise ValueError("At least one finite IQR value is required")
    if np.any(finite < 0):
        raise ValueError("IQR values cannot be negative")
    return float(np.quantile(finite, quantile))


def interquartile_range(values: ArrayLike, *, axis: int | None = None) -> NDArray[np.float64]:
    """Compute the NaN-aware 75th minus 25th percentile."""

    array = np.asarray(values, dtype=float)
    return np.asarray(
        np.nanquantile(array, 0.75, axis=axis) - np.nanquantile(array, 0.25, axis=axis)
    )
