"""Scientific constants and fixed conventions used by the pipeline."""

from __future__ import annotations

AVOGADRO = 6.022_140_76e23
"""Avogadro constant in molecules per mole (exact SI value)."""

CO_MOLAR_MASS_KG_PER_MOL = 28.0101e-3
"""Molar mass of carbon monoxide in kilograms per mole."""

DRY_AIR_MOLAR_MASS_KG_PER_MOL = 28.9647e-3
"""Molar mass of dry air used to integrate MERRA-2 CO volume mixing ratio."""

STANDARD_GRAVITY_M_PER_S2 = 9.80665
"""Standard acceleration due to gravity in metres per second squared."""

SQUARE_METRES_PER_SQUARE_CENTIMETRE = 1.0e4
INTERNAL_CO_UNIT = "mol/cm²"
SUPPORTED_CO_UNITS = frozenset({"mol/m²", "mol/cm²", "kg/m²", "molecules/cm²"})

REPORT_GRID_SHAPE = (131, 225)
REPORT_CORRECTION_BOUNDS = (0.2, 5.0)
REPORT_RANDOM_SEED = 42
