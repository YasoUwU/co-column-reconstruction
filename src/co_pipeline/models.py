"""Small deterministic empirical QM and QDM reference implementations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _training_values(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float).ravel()
    finite = array[np.isfinite(array)]
    if finite.size < 2:
        raise ValueError(f"{name} requires at least two finite training values")
    return np.sort(finite)


def _plotting_positions(size: int) -> NDArray[np.float64]:
    return (np.arange(size, dtype=float) + 0.5) / size


def _empirical_probabilities(
    values: NDArray[np.float64], sorted_reference: NDArray[np.float64]
) -> NDArray[np.float64]:
    ranks = np.searchsorted(sorted_reference, values, side="right")
    probabilities = (ranks - 0.5) / sorted_reference.size
    return np.clip(probabilities, 0.0, 1.0)


@dataclass
class QuantileMapper:
    """Empirical quantile mapping fitted solely from paired training distributions."""

    source_sorted_: NDArray[np.float64] | None = None
    target_sorted_: NDArray[np.float64] | None = None

    def fit(self, source_train: ArrayLike, target_train: ArrayLike) -> QuantileMapper:
        self.source_sorted_ = _training_values(source_train, name="source_train")
        self.target_sorted_ = _training_values(target_train, name="target_train")
        return self

    def predict(self, source: ArrayLike) -> NDArray[np.float64]:
        if self.source_sorted_ is None or self.target_sorted_ is None:
            raise RuntimeError("QuantileMapper must be fitted before prediction")
        values = np.asarray(source, dtype=float)
        output = np.full(values.shape, np.nan, dtype=float)
        finite = np.isfinite(values)
        probabilities = _empirical_probabilities(values[finite], self.source_sorted_)
        output[finite] = np.interp(
            probabilities, _plotting_positions(self.target_sorted_.size), self.target_sorted_
        )
        return output


@dataclass
class QuantileDeltaMapper:
    """Multiplicative empirical QDM for positive CO total columns.

    The quantile-wise training correction factor is applied to each prediction.
    This preserves relative changes while avoiding any access to evaluation targets.
    """

    source_sorted_: NDArray[np.float64] | None = None
    ratio_quantiles_: NDArray[np.float64] | None = None
    probabilities_: NDArray[np.float64] | None = None
    n_quantiles: int = 101

    def fit(self, source_train: ArrayLike, target_train: ArrayLike) -> QuantileDeltaMapper:
        source = _training_values(source_train, name="source_train")
        target = _training_values(target_train, name="target_train")
        if np.any(source <= 0) or np.any(target <= 0):
            raise ValueError("Multiplicative QDM requires strictly positive training values")
        if self.n_quantiles < 2:
            raise ValueError("n_quantiles must be at least two")
        probabilities = np.linspace(0.0, 1.0, self.n_quantiles)
        source_quantiles = np.quantile(source, probabilities)
        target_quantiles = np.quantile(target, probabilities)
        self.source_sorted_ = source
        self.ratio_quantiles_ = target_quantiles / source_quantiles
        self.probabilities_ = probabilities
        return self

    def predict(self, source: ArrayLike) -> NDArray[np.float64]:
        if (
            self.source_sorted_ is None
            or self.ratio_quantiles_ is None
            or self.probabilities_ is None
        ):
            raise RuntimeError("QuantileDeltaMapper must be fitted before prediction")
        values = np.asarray(source, dtype=float)
        output = np.full(values.shape, np.nan, dtype=float)
        finite = np.isfinite(values)
        if np.any(values[finite] <= 0):
            raise ValueError("Multiplicative QDM requires strictly positive prediction values")
        probabilities = _empirical_probabilities(values[finite], self.source_sorted_)
        ratios = np.interp(probabilities, self.probabilities_, self.ratio_quantiles_)
        output[finite] = values[finite] * ratios
        return output


EmpiricalQuantileMapping = QuantileMapper
EmpiricalQuantileDeltaMapping = QuantileDeltaMapper


@dataclass(frozen=True)
class GriddedStatisticalCalibration:
    """Cell-wise LS/QM/QDM parameters with a global fallback for sparse cells."""

    factor: NDArray[np.float64]
    source_quantiles: NDArray[np.float64]
    target_quantiles: NDArray[np.float64]
    probabilities: NDArray[np.float64]


def _strictly_increasing(values: NDArray[np.float64]) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=float).copy()
    for index in range(1, result.size):
        if result[index] <= result[index - 1]:
            result[index] = result[index - 1] + 1.0e-12
    return result


def fit_gridded_statistical_calibration(
    source: ArrayLike,
    target: ArrayLike,
    *,
    n_quantiles: int = 10,
    minimum_cell_samples: int = 20,
    correction_bounds: tuple[float, float] = (0.2, 5.0),
) -> GriddedStatisticalCalibration:
    """Fit historical cell-wise statistical corrections with global fallback."""

    source_cube = np.asarray(source, dtype=float)
    target_cube = np.asarray(target, dtype=float)
    if source_cube.shape != target_cube.shape or source_cube.ndim != 3:
        raise ValueError("source and target must be matching (time, lat, lon) cubes")
    if n_quantiles < 2 or minimum_cell_samples < 2:
        raise ValueError("n_quantiles and minimum_cell_samples must be at least two")
    valid = (
        np.isfinite(source_cube) & np.isfinite(target_cube) & (source_cube > 0) & (target_cube > 0)
    )
    if valid.sum() < 2:
        raise ValueError("At least two valid source-target pairs are required")
    time, n_lat, n_lon = source_cube.shape
    source_flat = source_cube.reshape(time, -1)
    target_flat = target_cube.reshape(time, -1)
    valid_flat = valid.reshape(time, -1)
    probabilities = np.linspace(0.0, 1.0, n_quantiles + 1)
    global_source = source_cube[valid]
    global_target = target_cube[valid]
    global_factor = float(np.mean(global_target) / np.mean(global_source))
    global_source_quantiles = _strictly_increasing(np.quantile(global_source, probabilities))
    global_target_quantiles = _strictly_increasing(np.quantile(global_target, probabilities))
    factor = np.full(source_flat.shape[1], global_factor)
    source_quantiles = np.repeat(global_source_quantiles[:, None], source_flat.shape[1], axis=1)
    target_quantiles = np.repeat(global_target_quantiles[:, None], source_flat.shape[1], axis=1)
    for cell in range(source_flat.shape[1]):
        selected = valid_flat[:, cell]
        if selected.sum() < minimum_cell_samples:
            continue
        source_cell = source_flat[selected, cell]
        target_cell = target_flat[selected, cell]
        factor[cell] = np.sum(target_cell) / np.sum(source_cell)
        source_quantiles[:, cell] = _strictly_increasing(np.quantile(source_cell, probabilities))
        target_quantiles[:, cell] = _strictly_increasing(np.quantile(target_cell, probabilities))
    factor = np.clip(factor, *correction_bounds).reshape(n_lat, n_lon)
    return GriddedStatisticalCalibration(
        factor=factor,
        source_quantiles=source_quantiles.reshape(n_quantiles + 1, n_lat, n_lon),
        target_quantiles=target_quantiles.reshape(n_quantiles + 1, n_lat, n_lon),
        probabilities=probabilities,
    )


def apply_gridded_statistical_calibration(
    source: ArrayLike, calibration: GriddedStatisticalCalibration
) -> dict[str, NDArray[np.float64]]:
    """Apply historical cell-wise LS, QM and multiplicative QDM corrections."""

    field = np.asarray(source, dtype=float)
    if field.shape != calibration.factor.shape:
        raise ValueError("source field shape does not match calibration grid")
    linear = field * calibration.factor
    qm = np.full(field.shape, np.nan)
    qdm = np.full(field.shape, np.nan)
    for cell in zip(*np.where(np.isfinite(field) & (field > 0)), strict=True):
        value = field[cell]
        source_quantiles = calibration.source_quantiles[(slice(None), *cell)]
        target_quantiles = calibration.target_quantiles[(slice(None), *cell)]
        qm[cell] = np.interp(
            value,
            source_quantiles,
            target_quantiles,
            left=target_quantiles[0],
            right=target_quantiles[-1],
        )
        probability = np.interp(
            value,
            source_quantiles,
            calibration.probabilities,
            left=0.0,
            right=1.0,
        )
        target_at_probability = np.interp(probability, calibration.probabilities, target_quantiles)
        source_at_probability = np.interp(probability, calibration.probabilities, source_quantiles)
        relative_change = np.clip(value / max(source_at_probability, 1.0e-30), 0.5, 2.0)
        qdm[cell] = target_at_probability * relative_change
    return {"LS": linear, "QM": qm, "QDM": qdm}
