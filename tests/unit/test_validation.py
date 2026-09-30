import numpy as np
import pytest

from co_pipeline.validation import (
    interquartile_range,
    regional_iqr_threshold,
    satellite_consensus,
    satellite_median,
)


def test_satellite_median_requires_configured_coverage():
    anomalies = np.array([[1.0, 2.0, np.nan], [3.0, np.nan, np.nan], [5.0, 4.0, 7.0]])
    median, count = satellite_median(anomalies, minimum_satellites=2)
    np.testing.assert_allclose(median[:2], [3.0, 3.0])
    assert np.isnan(median[2])
    np.testing.assert_array_equal(count, [3, 2, 1])


def test_consensus_applies_neutral_tolerance_and_three_satellite_rule():
    anomalies = np.array(
        [
            [0.5, -0.8, 0.1, 0.6],
            [0.7, -1.0, 0.2, 0.9],
            [0.8, -0.6, -0.1, np.nan],
        ]
    )
    result = satellite_consensus(
        anomalies, minimum_satellites=2, strong_satellites=3, neutral_tolerance=0.25
    )
    np.testing.assert_array_equal(result.direction, [1, -1, 0, 1])
    np.testing.assert_array_equal(result.strong_agreement, [True, True, False, False])


def test_neutral_interval_is_strict_at_quarter_sigma():
    result = satellite_consensus(
        np.array([[0.25, -0.25], [0.25, -0.25], [0.25, -0.25]]),
        minimum_satellites=2,
        strong_satellites=3,
        neutral_tolerance=0.25,
    )
    np.testing.assert_array_equal(result.direction, [1, -1])
    np.testing.assert_array_equal(result.strong_agreement, [True, True])


def test_iqr_and_one_third_threshold_are_parameterized():
    samples = np.array([[0.0, 1.0, 2.0, 3.0], [0.0, 2.0, 4.0, 6.0]])
    iqrs = interquartile_range(samples, axis=1)
    np.testing.assert_allclose(iqrs, [1.5, 3.0])
    assert regional_iqr_threshold([1.0, 2.0, 3.0, np.nan], quantile=1 / 3) == pytest.approx(5 / 3)


def test_iqr_threshold_rejects_invalid_configuration():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        regional_iqr_threshold([1.0], quantile=1.1)
    with pytest.raises(ValueError, match="finite"):
        regional_iqr_threshold([np.nan])
