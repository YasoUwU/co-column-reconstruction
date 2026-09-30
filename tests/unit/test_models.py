import pickle

import numpy as np
import pytest

from co_pipeline.models import (
    QuantileDeltaMapper,
    QuantileMapper,
    apply_gridded_statistical_calibration,
    fit_gridded_statistical_calibration,
)


def test_quantile_mapping_uses_training_distributions():
    model = QuantileMapper().fit([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0])
    prediction = model.predict([1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(prediction, [10.0, 20.0, 30.0, 40.0])


def test_multiplicative_qdm_preserves_training_quantile_factor():
    model = QuantileDeltaMapper().fit([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
    np.testing.assert_allclose(model.predict([1.5, 3.5]), [3.0, 7.0], rtol=1e-12)


def test_qm_and_qdm_preserve_missing_predictions():
    qm = QuantileMapper().fit([1.0, 2.0], [10.0, 20.0])
    qdm = QuantileDeltaMapper().fit([1.0, 2.0], [2.0, 4.0])
    assert np.isnan(qm.predict([np.nan])[0])
    assert np.isnan(qdm.predict([np.nan])[0])


def test_qdm_rejects_non_positive_data():
    with pytest.raises(ValueError, match="strictly positive"):
        QuantileDeltaMapper().fit([0.0, 1.0], [1.0, 2.0])


def test_models_are_serializable_and_deterministic():
    fitted = QuantileMapper().fit([1.0, 2.0, 3.0], [2.0, 4.0, 8.0])
    restored = pickle.loads(pickle.dumps(fitted))
    values = np.array([1.2, 2.8])
    np.testing.assert_array_equal(restored.predict(values), fitted.predict(values))


def test_gridded_calibration_is_cell_specific_with_global_fallback():
    source = np.ones((3, 1, 2))
    target = np.array([[[2.0, 4.0]], [[2.0, np.nan]], [[2.0, np.nan]]])
    calibration = fit_gridded_statistical_calibration(
        source,
        target,
        n_quantiles=2,
        minimum_cell_samples=2,
    )
    predictions = apply_gridded_statistical_calibration(np.ones((1, 2)), calibration)
    np.testing.assert_allclose(predictions["LS"][0, 0], 2.0)
    # The sparse second cell receives the pooled global factor, not the first cell's factor.
    np.testing.assert_allclose(predictions["LS"][0, 1], 2.5)
