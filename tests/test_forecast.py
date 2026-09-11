"""Tests for the empirical probabilistic forecaster."""

import numpy as np

from aquareserve.weather.forecast import EmpiricalForecaster


def test_empty_forecaster_returns_zeros():
    fc = EmpiricalForecaster(window=10)
    et0, rain = fc.mean(5)

    assert et0 == [0.0] * 5 and rain == [0.0] * 5

    scen = fc.scenarios(5, 3)

    assert len(scen) == 3
    assert all(len(s[0]) == 5 for s in scen)


def test_scenarios_shape_and_bounds():
    fc = EmpiricalForecaster(window=20, seed=1)

    for e, r in zip([4, 5, 6, 7, 8], [0, 2, 0, 0, 5], strict=True):
        fc.observe(e, r)

    scen = fc.scenarios(horizon=12, n=8)

    assert len(scen) == 8

    for et0, rain in scen:
        assert len(et0) == 12 and len(rain) == 12

        # resampled values must come from the observed set
        assert set(et0).issubset({4.0, 5.0, 6.0, 7.0, 8.0})
        assert set(rain).issubset({0.0, 2.0, 5.0})


def test_mean_matches_window_average():
    fc = EmpiricalForecaster(window=5)

    for e in [3, 5, 7]:
        fc.observe(e, 1.0)

    et0, rain = fc.mean(4)

    assert np.allclose(et0, [5.0] * 4)
    assert np.allclose(rain, [1.0] * 4)


def test_seed_is_deterministic():
    a = EmpiricalForecaster(window=10, seed=42)
    b = EmpiricalForecaster(window=10, seed=42)

    for e in [4, 6, 8, 5]:
        a.observe(e, 0.0)
        b.observe(e, 0.0)

    assert a.scenarios(6, 4) == b.scenarios(6, 4)


def test_window_evicts_old_observations():
    fc = EmpiricalForecaster(window=3)

    for e in [1, 2, 3, 9, 9, 9]:
        fc.observe(e, 0.0)

    et0, _ = fc.mean(2)
    
    assert np.allclose(et0, [9.0, 9.0])
