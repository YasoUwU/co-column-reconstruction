"""Strict carbon-monoxide total-column unit conversions."""

from __future__ import annotations

from typing import TypeVar

import numpy as np

from .constants import (
    AVOGADRO,
    CO_MOLAR_MASS_KG_PER_MOL,
    INTERNAL_CO_UNIT,
    SQUARE_METRES_PER_SQUARE_CENTIMETRE,
    SUPPORTED_CO_UNITS,
)

ArrayLike = TypeVar("ArrayLike")


def validate_co_unit(unit: str) -> str:
    """Return *unit* unchanged when it is one of the four supported units.

    No aliases are accepted: silently guessing a unit is too risky for total-column
    products whose magnitudes differ by many orders.
    """

    if unit not in SUPPORTED_CO_UNITS:
        supported = ", ".join(sorted(SUPPORTED_CO_UNITS))
        raise ValueError(f"Unsupported CO unit {unit!r}; expected one of: {supported}")
    return unit


def to_mol_per_cm2(values: ArrayLike, unit: str) -> ArrayLike:
    """Convert CO total-column values to the canonical ``mol/cm²`` unit."""

    validate_co_unit(unit)
    if unit == INTERNAL_CO_UNIT:
        return values
    if unit == "mol/m²":
        return values / SQUARE_METRES_PER_SQUARE_CENTIMETRE
    if unit == "kg/m²":
        return values / CO_MOLAR_MASS_KG_PER_MOL / SQUARE_METRES_PER_SQUARE_CENTIMETRE
    return values / AVOGADRO


def from_mol_per_cm2(values: ArrayLike, unit: str) -> ArrayLike:
    """Convert canonical ``mol/cm²`` values to a supported output unit."""

    validate_co_unit(unit)
    if unit == INTERNAL_CO_UNIT:
        return values
    if unit == "mol/m²":
        return values * SQUARE_METRES_PER_SQUARE_CENTIMETRE
    if unit == "kg/m²":
        return values * SQUARE_METRES_PER_SQUARE_CENTIMETRE * CO_MOLAR_MASS_KG_PER_MOL
    return values * AVOGADRO


def convert_co_column(values: ArrayLike, from_unit: str, to_unit: str) -> ArrayLike:
    """Convert values between any two explicitly supported CO column units."""

    validate_co_unit(from_unit)
    validate_co_unit(to_unit)
    if from_unit == to_unit:
        return values
    return from_mol_per_cm2(to_mol_per_cm2(values, from_unit), to_unit)


def assert_finite_nonnegative(values: object, *, name: str = "CO column") -> None:
    """Reject non-finite or negative physical column values."""

    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")
    if np.any(array < 0):
        raise ValueError(f"{name} contains negative values")
