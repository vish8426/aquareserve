"""Tests for the weather loader, synthetic generator and drought injection."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.weather import columns as C
from aquareserve.weather import generate_weather, load_weather
from aquareserve.weather.drought import find_scenario

FIXTURE = Path(__file__).parent / "fixtures" / "silo_sample.txt"


@pytest.fixture
def climate(example_farm_path: Path):

    # Deep copy so tests can mutate path/period without side effects.
    return load_scenario(example_farm_path).climate.model_copy(deep=True)


def test_synthetic_is_deterministic():
    a = generate_weather("2001-01-01", "2001-12-31", latitude_deg=-34.0, elevation_m=50.0, seed=7)
    b = generate_weather("2001-01-01", "2001-12-31", latitude_deg=-34.0, elevation_m=50.0, seed=7)

    assert a.equals(b)


def test_different_seeds_differ():
    a = generate_weather("2001-01-01", "2001-12-31", latitude_deg=-34.0, elevation_m=50.0, seed=1)
    b = generate_weather("2001-01-01", "2001-12-31", latitude_deg=-34.0, elevation_m=50.0, seed=2)

    assert not a.equals(b)


def test_canonical_columns_and_ranges():
    df = generate_weather("2001-01-01", "2001-12-31", latitude_deg=-34.0, elevation_m=50.0, seed=0)

    for col in C.ALL_COLUMNS:
        assert col in df.columns

    assert (df[C.RAIN] >= 0).all()
    assert (df[C.ET0] >= 0).all()
    assert (df[C.TMAX] >= df[C.TMIN]).all()
    assert len(df) == 365


def test_loader_reads_real_silo_when_present(climate):

    # Point the config at the committed real fixture (Jan 2000).
    climate.dataset.path = str(FIXTURE)
    climate.period.start = "2000-01-01"
    climate.period.end = "2000-01-31"

    df = load_weather(climate)

    assert len(df) == 29

    # real Mildura summer demand
    assert df[C.ET0].mean() > 4.0  


def test_loader_falls_back_to_synthetic_when_file_absent(climate):

    # Force a missing file -> deterministic synthetic fallback for the period.
    climate.dataset.path = "data/raw/does_not_exist.txt"
    climate.period.start = "2001-01-01"
    climate.period.end = "2001-12-31"

    df = load_weather(climate, seed=0)

    assert len(df) == 365
    assert set(C.ALL_COLUMNS) <= set(df.columns)


def test_drought_injection_scales_rain_and_et0(climate):

    # Use synthetic (bogus path) so the base is environment-independent.
    climate.dataset.path = "data/raw/does_not_exist.txt"
    climate.period.start = "2001-01-01"
    climate.period.end = "2001-12-31"

    normal = load_weather(climate, scenario_name="normal", seed=0)
    severe = load_weather(climate, scenario_name="severe", seed=0)
    sev = find_scenario(climate.drought_scenarios, "severe")
    
    assert severe[C.RAIN].sum() == pytest.approx(normal[C.RAIN].sum() * sev.rainfall_multiplier, rel=1e-6)
    assert severe[C.ET0].sum() == pytest.approx(normal[C.ET0].sum() * sev.et0_multiplier, rel=1e-6)


def test_find_scenario_unknown_raises(climate):
    with pytest.raises(KeyError):
        find_scenario(climate.drought_scenarios, "apocalypse")
