from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

from co_pipeline.features import build_abcd_features, log_ratio_target, reconstruct_positive_column
from co_pipeline.gridding import grid_inverse_variance
from co_pipeline.merra2 import daily_mean_eight_steps, integrate_co_column
from co_pipeline.validation import satellite_median


def test_two_day_three_by_four_synthetic_workflow() -> None:
    latitude = np.array([-1.0, 0.0, 1.0])
    longitude = np.array([10.0, 11.0, 12.0, 13.0])
    observations = np.full((3, 4), 2.2e-5)

    gridded = grid_inverse_variance(
        np.repeat(latitude, 4),
        np.tile(longitude, 3),
        observations.ravel(),
        np.full(12, 1.0e-7),
        latitude,
        longitude,
    )
    assert np.allclose(gridded.value, observations)

    co_mass_mixing_ratio = np.full((8, 2, 3, 4), 1.0e-7)
    pressure_thickness = np.full_like(co_mass_mixing_ratio, 5_000.0)
    instantaneous = integrate_co_column(co_mass_mixing_ratio, pressure_thickness, level_axis=1)
    source_day_one = daily_mean_eight_steps(instantaneous, time_axis=0)
    source_day_two = source_day_one * 1.05

    feature_rows = []
    targets = []
    for day, source in (("20230801", source_day_one), ("20230802", source_day_two)):
        feature_rows.append(
            build_abcd_features(
                source,
                latitude,
                longitude,
                day,
                frp_mean=1.0,
                frp_total=2.0,
                severity_score=0.5,
            )
        )
        targets.append(log_ratio_target(source * 1.1, source).ravel())
    features = np.vstack(feature_rows)
    target = np.concatenate(targets)
    estimator = Ridge(alpha=1.0).fit(features, target)
    corrected = reconstruct_positive_column(
        source_day_two.ravel(), estimator.predict(feature_rows[1])
    )
    assert corrected.shape == (12,)
    assert np.all(corrected > 0)

    median, count = satellite_median(
        np.stack([corrected, corrected * 1.01, np.full_like(corrected, np.nan)]),
        minimum_satellites=2,
    )
    assert np.all(count == 2)
    assert np.all(np.isfinite(median))
