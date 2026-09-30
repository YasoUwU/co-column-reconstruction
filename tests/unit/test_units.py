import numpy as np
import pytest

from co_pipeline.constants import AVOGADRO, CO_MOLAR_MASS_KG_PER_MOL
from co_pipeline.units import convert_co_column, to_mol_per_cm2


@pytest.mark.parametrize(
    ("unit", "input_value"),
    [
        ("mol/cm²", 1.0),
        ("mol/m²", 1.0e4),
        ("kg/m²", CO_MOLAR_MASS_KG_PER_MOL * 1.0e4),
        ("molecules/cm²", AVOGADRO),
    ],
)
def test_all_supported_units_convert_to_one_mol_per_cm2(unit, input_value):
    assert to_mol_per_cm2(np.array([input_value]), unit)[0] == pytest.approx(1.0)


@pytest.mark.parametrize("unit", ["mol m-2", "molec/cm2", "ppb", ""])
def test_unknown_or_aliased_units_are_rejected(unit):
    with pytest.raises(ValueError, match="Unsupported CO unit"):
        convert_co_column(np.array([1.0]), unit, "mol/cm²")


def test_round_trip_between_every_supported_unit():
    units = ["mol/m²", "mol/cm²", "kg/m²", "molecules/cm²"]
    original = np.array([1.0e-6, 2.5e-5])
    for unit in units:
        converted = convert_co_column(original, "mol/cm²", unit)
        restored = convert_co_column(converted, unit, "mol/cm²")
        np.testing.assert_allclose(restored, original, rtol=1e-14)
