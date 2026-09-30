"""MERRA-2 vertical integration and daily aggregation."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .constants import (
    DRY_AIR_MOLAR_MASS_KG_PER_MOL,
    SQUARE_METRES_PER_SQUARE_CENTIMETRE,
    STANDARD_GRAVITY_M_PER_S2,
)


def integrate_co_column(
    co_volume_mixing_ratio: ArrayLike,
    layer_pressure_thickness_pa: ArrayLike,
    *,
    level_axis: int = -1,
    gravity: float = STANDARD_GRAVITY_M_PER_S2,
) -> NDArray[np.float64]:
    """Integrate MERRA-2 CO volume mixing ratio using ``sum(CO * DELP / g)``.

    Inputs are respectively mol(CO)/mol(air) and Pa. The returned total column is
    expressed in the pipeline's canonical unit, mol/cm².
    """

    mixing_ratio = np.asarray(co_volume_mixing_ratio, dtype=float)
    delp = np.asarray(layer_pressure_thickness_pa, dtype=float)
    if mixing_ratio.shape != delp.shape:
        raise ValueError("CO mixing ratio and DELP must have identical shapes")
    if not np.isfinite(gravity) or gravity <= 0:
        raise ValueError("gravity must be finite and positive")
    if np.any(np.isfinite(delp) & (delp < 0)):
        raise ValueError("DELP cannot be negative")
    column_mol_per_m2 = np.sum(mixing_ratio * delp / gravity, axis=level_axis)
    column_mol_per_m2 /= DRY_AIR_MOLAR_MASS_KG_PER_MOL
    return column_mol_per_m2 / SQUARE_METRES_PER_SQUARE_CENTIMETRE


def daily_mean_eight_steps(
    instantaneous_columns: ArrayLike, *, time_axis: int = 0, require_complete: bool = True
) -> NDArray[np.float64]:
    """Average the eight three-hourly MERRA-2 fields of a complete UTC day."""

    values = np.asarray(instantaneous_columns, dtype=float)
    axis = time_axis + values.ndim if time_axis < 0 else time_axis
    if not 0 <= axis < values.ndim:
        raise ValueError(f"time_axis {time_axis} is out of bounds for {values.ndim} dimensions")
    if require_complete and values.shape[axis] != 8:
        raise ValueError(
            f"A complete MERRA-2 day requires 8 time steps; received {values.shape[axis]}"
        )
    if values.shape[axis] == 0:
        raise ValueError("Cannot average an empty time axis")
    # The historical workflow requires all eight timestamps but uses a NaN-aware
    # mean at individual grid cells.
    return np.nanmean(values, axis=axis)
