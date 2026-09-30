import numpy as np
import pytest

from co_pipeline.cams import normalize_cams_column
from co_pipeline.constants import (
    CO_MOLAR_MASS_KG_PER_MOL,
    DRY_AIR_MOLAR_MASS_KG_PER_MOL,
    STANDARD_GRAVITY_M_PER_S2,
)
from co_pipeline.merra2 import daily_mean_eight_steps, integrate_co_column


def test_merra2_delp_integration_has_expected_units():
    mixing_ratio = np.full((2, 3), DRY_AIR_MOLAR_MASS_KG_PER_MOL)
    delp = np.full((2, 3), STANDARD_GRAVITY_M_PER_S2)
    result = integrate_co_column(mixing_ratio, delp, level_axis=1)
    # A mol/mol mixing ratio equal to M_air yields one mol m-2 per layer here.
    np.testing.assert_allclose(result, np.full(2, 3.0e-4))


def test_merra2_daily_mean_requires_eight_timestamps_and_skips_spatial_nan():
    fields = np.arange(8 * 2, dtype=float).reshape(8, 2)
    np.testing.assert_allclose(daily_mean_eight_steps(fields), fields.mean(axis=0))
    with pytest.raises(ValueError, match="requires 8"):
        daily_mean_eight_steps(fields[:7])
    fields[3, 0] = np.nan
    np.testing.assert_allclose(daily_mean_eight_steps(fields), np.nanmean(fields, axis=0))


def test_cams_kg_per_m2_is_converted_to_internal_unit():
    result = normalize_cams_column(np.array([CO_MOLAR_MASS_KG_PER_MOL * 1.0e4]))
    np.testing.assert_allclose(result, [1.0])


def test_cams_rejects_negative_columns():
    with pytest.raises(ValueError, match="negative"):
        normalize_cams_column(np.array([-1.0]))
