"""Uncertainty-aware gridding for irregular IASI observations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class GriddedObservations:
    """Weighted grid values, propagated uncertainty, and observation count."""

    value: NDArray[np.float64]
    uncertainty: NDArray[np.float64]
    count: NDArray[np.int64]


def inverse_variance_mean(
    values: ArrayLike, uncertainties: ArrayLike, *, axis: int | tuple[int, ...] | None = None
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the ``1/sigma²`` mean and its independent-error uncertainty."""

    value = np.asarray(values, dtype=float)
    sigma = np.asarray(uncertainties, dtype=float)
    if value.shape != sigma.shape:
        raise ValueError("values and uncertainties must have the same shape")
    valid = np.isfinite(value) & np.isfinite(sigma) & (sigma > 0)
    weights = np.zeros(sigma.shape, dtype=float)
    np.divide(1.0, np.square(sigma), out=weights, where=valid)
    numerator = np.sum(np.where(valid, value * weights, 0.0), axis=axis)
    denominator = np.sum(weights, axis=axis)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = np.where(denominator > 0, numerator / denominator, np.nan)
        propagated = np.where(denominator > 0, np.sqrt(1.0 / denominator), np.nan)
    return np.asarray(mean), np.asarray(propagated)


def _centres_to_edges(centres: NDArray[np.float64]) -> NDArray[np.float64]:
    if centres.ndim != 1 or centres.size < 2:
        raise ValueError("Grid coordinates must be one-dimensional with at least two centres")
    differences = np.diff(centres)
    if np.any(differences <= 0):
        raise ValueError("Grid centres must be strictly increasing")
    midpoints = centres[:-1] + differences / 2
    return np.concatenate(
        ([centres[0] - differences[0] / 2], midpoints, [centres[-1] + differences[-1] / 2])
    )


def grid_inverse_variance(
    latitude: ArrayLike,
    longitude: ArrayLike,
    values: ArrayLike,
    uncertainties: ArrayLike,
    grid_latitude: ArrayLike,
    grid_longitude: ArrayLike,
) -> GriddedObservations:
    """Bin observations to grid centres using inverse-variance weighting.

    Observations outside the outer cell edges and observations with invalid values
    or non-positive uncertainty are ignored.
    """

    lat = np.asarray(latitude, dtype=float).ravel()
    lon = np.asarray(longitude, dtype=float).ravel()
    value = np.asarray(values, dtype=float).ravel()
    sigma = np.asarray(uncertainties, dtype=float).ravel()
    if not (lat.size == lon.size == value.size == sigma.size):
        raise ValueError("Observation arrays must contain the same number of elements")
    grid_lat = np.asarray(grid_latitude, dtype=float)
    grid_lon = np.asarray(grid_longitude, dtype=float)
    lat_edges = _centres_to_edges(grid_lat)
    lon_edges = _centres_to_edges(grid_lon)
    lat_index = np.searchsorted(lat_edges, lat, side="right") - 1
    lon_index = np.searchsorted(lon_edges, lon, side="right") - 1
    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(value)
        & np.isfinite(sigma)
        & (sigma > 0)
        & (lat_index >= 0)
        & (lat_index < grid_lat.size)
        & (lon_index >= 0)
        & (lon_index < grid_lon.size)
    )
    shape = (grid_lat.size, grid_lon.size)
    weight_sum = np.zeros(shape, dtype=float)
    weighted_sum = np.zeros(shape, dtype=float)
    count = np.zeros(shape, dtype=np.int64)
    weight = 1.0 / np.square(sigma[valid])
    indices = (lat_index[valid], lon_index[valid])
    np.add.at(weight_sum, indices, weight)
    np.add.at(weighted_sum, indices, value[valid] * weight)
    np.add.at(count, indices, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(weight_sum > 0, weighted_sum / weight_sum, np.nan)
        uncertainty = np.where(weight_sum > 0, np.sqrt(1.0 / weight_sum), np.nan)
    return GriddedObservations(result, uncertainty, count)
