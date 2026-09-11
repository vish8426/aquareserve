"""Tests for the root-zone Extended Kalman Filter."""

from __future__ import annotations

import numpy as np
import pytest

from aquareserve.estimation import RootZoneEKF
from aquareserve.models import SoilWaterBalance


def test_validates_parameters():
    with pytest.raises(ValueError):
        RootZoneEKF(taw_mm=0.0, depletion_fraction_p=0.5)

    with pytest.raises(ValueError):
        RootZoneEKF(taw_mm=100.0, depletion_fraction_p=1.5)


def test_predict_matches_balance_model_unstressed():
    # On a dry, unstressed day the EKF mean must advance exactly like the balance.
    taw, p, dr0 = 200.0, 0.5, 20.0
    ekf = RootZoneEKF(taw, p, dr0)
    swb = SoilWaterBalance(taw, p, dr0)
    step = swb.step(rain_mm=0.0, crop_et_mm=6.0)
    ekf.predict(rain_mm=0.0, crop_et_mm=6.0)

    assert ekf.depletion_mm == pytest.approx(step.depletion_mm)


def test_variance_grows_on_predict_and_shrinks_on_update():
    ekf = RootZoneEKF(200.0, 0.5, 20.0, initial_variance=50.0, process_variance=4.0)
    p0 = ekf.state.variance
    ekf.predict(rain_mm=0.0, crop_et_mm=5.0)

    # uncertainty grows without data
    assert ekf.state.variance > p0  
    ekf.update(measurement_mm=25.0)

    # update reduces uncertainty
    assert ekf.state.variance < ekf.P + ekf.R  


def test_update_moves_estimate_toward_measurement():
    ekf = RootZoneEKF(200.0, 0.5, 20.0, initial_variance=100.0, measurement_variance=25.0)
    ekf.update(measurement_mm=60.0)

    # partial correction toward the reading
    assert 20.0 < ekf.depletion_mm < 60.0  


def test_ekf_beats_raw_sensor_on_noisy_season():
    """The headline: fusing a noisy sensor with the model beats the raw sensor."""
    taw, p = 150.0, 0.55
    rng = np.random.default_rng(1)
    true = SoilWaterBalance(taw, p, 60.0)
    ekf = RootZoneEKF(taw, p, 60.0, measurement_variance=18.0**2)
    noise_sd, meas_every = 18.0, 3
    t_hist, s_hist, e_hist = [], [], []

    for day in range(180):
        etc = rng.uniform(3.0, 7.0)
        rain = rng.choice([0.0, 0.0, 0.0, 12.0])
        step = true.step(rain_mm=rain, crop_et_mm=etc)
        ekf.predict(rain_mm=rain, crop_et_mm=etc)

        if day % meas_every == 0:
            z = step.depletion_mm + rng.normal(0, noise_sd)
            ekf.update(z)
            s_hist.append(z)
            t_hist.append(step.depletion_mm)

        e_hist.append((ekf.depletion_mm, step.depletion_mm))

    rmse_sensor = np.sqrt(np.mean((np.array(s_hist) - np.array(t_hist)) ** 2))
    rmse_ekf = np.sqrt(np.mean([(e - t) ** 2 for e, t in e_hist]))

    # at least 40% error reduction
    assert rmse_ekf < 0.6 * rmse_sensor  


def test_estimate_stays_within_soil_bounds():
    ekf = RootZoneEKF(100.0, 0.5, 90.0)

    for _ in range(60):
        ekf.predict(rain_mm=0.0, crop_et_mm=10.0)

        assert 0.0 <= ekf.depletion_mm <= 100.0

    ekf.update(measurement_mm=999.0)  

    assert 0.0 <= ekf.depletion_mm <= 100.0
