"""CAMS total-column normalization helpers."""

from __future__ import annotations

from typing import TypeVar

from .units import assert_finite_nonnegative, to_mol_per_cm2

ArrayLike = TypeVar("ArrayLike")


def normalize_cams_column(values: ArrayLike, source_unit: str = "kg/m²") -> ArrayLike:
    """Validate and convert a CAMS total CO column to canonical ``mol/cm²``."""

    assert_finite_nonnegative(values, name="CAMS CO column")
    return to_mol_per_cm2(values, source_unit)
