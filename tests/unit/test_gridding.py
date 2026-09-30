import numpy as np

from co_pipeline.gridding import grid_inverse_variance, inverse_variance_mean


def test_inverse_variance_mean_and_propagated_uncertainty():
    mean, uncertainty = inverse_variance_mean([1.0, 3.0], [1.0, 2.0])
    np.testing.assert_allclose(mean, 1.4)
    np.testing.assert_allclose(uncertainty, np.sqrt(1.0 / 1.25))


def test_invalid_observations_do_not_contribute_to_weighted_mean():
    mean, uncertainty = inverse_variance_mean([1.0, 100.0, np.nan, 2.0], [1.0, 0.0, 1.0, np.nan])
    np.testing.assert_allclose(mean, 1.0)
    np.testing.assert_allclose(uncertainty, 1.0)


def test_grid_assigns_observations_and_reports_empty_cells():
    result = grid_inverse_variance(
        latitude=[-0.1, 0.1, 1.1, 20.0],
        longitude=[10.1, 9.9, 11.1, 20.0],
        values=[1.0, 3.0, 5.0, 999.0],
        uncertainties=[1.0, 1.0, 2.0, 1.0],
        grid_latitude=[0.0, 1.0],
        grid_longitude=[10.0, 11.0],
    )
    np.testing.assert_allclose(result.value[0, 0], 2.0)
    np.testing.assert_allclose(result.uncertainty[0, 0], 1 / np.sqrt(2))
    assert result.count[0, 0] == 2
    np.testing.assert_allclose(result.value[1, 1], 5.0)
    assert np.isnan(result.value[0, 1])
    assert result.count.sum() == 3


def test_grid_shape_matches_report_grid_contract():
    latitude = np.linspace(-65, 0, 131)
    longitude = np.linspace(-30, 82, 225)
    result = grid_inverse_variance([], [], [], [], latitude, longitude)
    assert result.value.shape == (131, 225)
    assert result.uncertainty.shape == (131, 225)
    assert result.count.shape == (131, 225)
