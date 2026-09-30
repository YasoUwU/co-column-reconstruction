import numpy as np
import pytest

from co_pipeline.features import (
    ABCD_FEATURE_NAMES,
    broadcast_monthly_domain_feature,
    build_abcd_features,
    log_ratio_target,
    reconstruct_positive_column,
    temporal_split,
)


def test_log_ratio_and_positive_reconstruction_are_inverse():
    source = np.array([1.0, 2.0, 4.0])
    observed = np.array([0.5, 3.0, 8.0])
    target = log_ratio_target(observed, source)
    np.testing.assert_allclose(reconstruct_positive_column(source, target), observed)


def test_reconstruction_clips_multiplicative_correction():
    source = np.array([2.0, 2.0])
    predictions = np.log([0.01, 100.0])
    np.testing.assert_allclose(reconstruct_positive_column(source, predictions), [0.4, 10.0])


def test_log_ratio_target_clips_report_correction_range():
    target = log_ratio_target([0.01, 100.0], [1.0, 1.0])
    np.testing.assert_allclose(target, np.log([0.2, 5.0]))


def test_log_ratio_rejects_non_positive_values():
    with pytest.raises(ValueError, match="strictly positive"):
        log_ratio_target([0.0], [1.0])


def test_temporal_split_has_no_leakage():
    years = np.arange(2012, 2025)
    split = temporal_split(
        years,
        train_start=2013,
        train_end=2017,
        evaluation_start=2018,
        evaluation_end=2024,
    )
    assert years[split.train].tolist() == [2013, 2014, 2015, 2016, 2017]
    assert years[split.evaluation].tolist() == list(range(2018, 2025))
    assert not np.any(split.train & split.evaluation)


def test_temporal_split_rejects_overlapping_intervals():
    with pytest.raises(ValueError, match="before evaluation"):
        temporal_split(
            [2017, 2018],
            train_start=2013,
            train_end=2018,
            evaluation_start=2018,
            evaluation_end=2024,
        )


def test_monthly_domain_feature_is_broadcast_by_index():
    result = broadcast_monthly_domain_feature([10.0, 20.0, 30.0], [2, 0, 2, 1])
    np.testing.assert_allclose(result, [30.0, 10.0, 30.0, 20.0])


def test_abcd_features_have_exact_canonical_order_and_values():
    assert ABCD_FEATURE_NAMES == (
        "log_CO_source",
        "lat",
        "lon",
        "sin_lat",
        "sin_lon",
        "cos_lon",
        "sin_month",
        "cos_month",
        "sin_doy",
        "cos_doy",
        "frp_mean",
        "frp_total",
        "severity_score",
        "log1p_frp_total",
    )
    source = np.array([[1.0, np.e], [np.e**2, np.e**3]])
    features = build_abcd_features(
        source,
        latitude=[0.0, 30.0],
        longitude=[0.0, 90.0],
        observation_date="20240901",
        frp_mean=2.0,
        frp_total=9.0,
        severity_score=4.0,
    )
    assert features.shape == (4, 14)
    np.testing.assert_allclose(features[:, 0], [0.0, 1.0, 2.0, 3.0])
    np.testing.assert_allclose(features[:, 1], [0.0, 0.0, 30.0, 30.0])
    np.testing.assert_allclose(features[:, 2], [0.0, 90.0, 0.0, 90.0])
    np.testing.assert_allclose(features[:, 3], [0.0, 0.0, 0.5, 0.5], atol=1e-15)
    np.testing.assert_allclose(features[:, 4], [0.0, 1.0, 0.0, 1.0], atol=1e-15)
    np.testing.assert_allclose(features[:, 5], [1.0, 0.0, 1.0, 0.0], atol=1e-15)
    np.testing.assert_allclose(features[:, 10], 2.0)
    np.testing.assert_allclose(features[:, 11], 9.0)
    np.testing.assert_allclose(features[:, 12], 4.0)
    np.testing.assert_allclose(features[:, 13], np.log1p(9.0))


def test_abcd_feature_mask_selects_rows_without_changing_columns():
    features = build_abcd_features(
        [[1.0, 2.0], [3.0, 4.0]],
        [0.0, 1.0],
        [10.0, 11.0],
        "2024-08-01",
        frp_mean=1.0,
        frp_total=2.0,
        severity_score=3.0,
        mask=[[False, True], [True, False]],
    )
    assert features.shape == (2, len(ABCD_FEATURE_NAMES))
    np.testing.assert_allclose(features[:, 0], np.log([2.0, 3.0]))
