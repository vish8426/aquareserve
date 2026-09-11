"""Tests for the Ensemble Kalman Filter root-zone estimator."""

from __future__ import annotations

import numpy as np
import pytest

from aquareserve.estimation import RootZoneEKF, RootZoneEnKF
from aquareserve.models import SoilWaterBalance


def test_validates_parameters():
    with pytest.raises(ValueError):
        RootZoneEnKF(taw_mm=0.0, depletion_fraction_p=0.5)

    with pytest.raises(ValueError):
        RootZoneEnKF(taw_mm=100.0, depletion_fraction_p=1.5)

    with pytest.raises(ValueError):
        RootZoneEnKF(taw_mm=100.0, depletion_fraction_p=0.5, ensemble_size=1)


def test_deterministic_with_seed():
    a = RootZoneEnKF(150.0, 0.5, 60.0, ensemble_size=40, seed=3)
    b = RootZoneEnKF(150.0, 0.5, 60.0, ensemble_size=40, seed=3)

    for _ in range(20):
        a.predict(0.0, 5.0)
        b.predict(0.0, 5.0)

    a.update(80.0)
    b.update(80.0)

    assert a.depletion_mm == pytest.approx(b.depletion_mm)


def test_estimate_stays_within_bounds():
    enkf = RootZoneEnKF(100.0, 0.5, 90.0, ensemble_size=30, seed=0)

    for _ in range(60):
        enkf.predict(0.0, 10.0)

        assert 0.0 <= enkf.depletion_mm <= 100.0

    enkf.update(999.0)

    assert 0.0 <= enkf.depletion_mm <= 100.0


def _run_filter_rmse(make_filter):
    taw, p = 150.0, 0.55
    rng = np.random.default_rng(1)
    truth = SoilWaterBalance(taw, p, 60.0)
    filt = make_filter(taw, p)
    noise_sd, every = 18.0, 3
    s_hist, t_hist, e_hist = [], [], []

    for day in range(180):
        etc = rng.uniform(3.0, 7.0)
        rain = rng.choice([0.0, 0.0, 0.0, 12.0])
        step = truth.step(rain_mm=rain, crop_et_mm=etc)
        filt.predict(rain_mm=rain, crop_et_mm=etc)

        if day % every == 0:
            z = step.depletion_mm + rng.normal(0, noise_sd)
            filt.update(z)
            s_hist.append(z)
            t_hist.append(step.depletion_mm)

        e_hist.append((filt.depletion_mm, step.depletion_mm))

    rmse_sensor = float(np.sqrt(np.mean((np.array(s_hist) - np.array(t_hist)) ** 2)))
    rmse_filt = float(np.sqrt(np.mean([(e - t) ** 2 for e, t in e_hist])))

    return rmse_sensor, rmse_filt


def test_enkf_beats_raw_sensor():
    rmse_sensor, rmse_enkf = _run_filter_rmse(lambda taw, p: RootZoneEnKF(taw, p, 60.0, measurement_variance=18.0**2, ensemble_size=60, seed=2))

    assert rmse_enkf < 0.6 * rmse_sensor


def test_enkf_and_ekf_agree_closely():
    _, rmse_enkf = _run_filter_rmse(
        lambda taw, p: RootZoneEnKF(taw, p, 60.0, measurement_variance=18.0**2, ensemble_size=80, seed=2)
    )
    
    _, rmse_ekf = _run_filter_rmse(
        lambda taw, p: RootZoneEKF(taw, p, 60.0, measurement_variance=18.0**2)
    )

    # For this mildly-nonlinear 1-D problem the two methods should be close.
    assert abs(rmse_enkf - rmse_ekf) < 2.0
