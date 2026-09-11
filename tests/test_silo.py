"""Tests for the real SILO fao56 station file parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.weather import columns as C
from aquareserve.weather.silo import read_silo_fao56

FIXTURE = Path(__file__).parent / "fixtures" / "silo_sample.txt"


def test_parses_canonical_columns():
    df = read_silo_fao56(FIXTURE)

    assert set(C.ALL_COLUMNS) <= set(df.columns)
    assert df.index.name == C.DATE

    # Jan 2000 rows in the fixture
    assert len(df) == 29  


def test_first_row_values_match_source():
    df = read_silo_fao56(FIXTURE)
    row = df.loc["2000-01-01"]

    assert row[C.TMAX] == pytest.approx(24.9)
    assert row[C.TMIN] == pytest.approx(10.7)
    assert row[C.RAIN] == pytest.approx(0.0)
    assert row[C.RS] == pytest.approx(31.9)
    assert row[C.ET0] == pytest.approx(6.1)

    # VP 8.8 hPa -> 0.88 kPa
    assert row[C.EA] == pytest.approx(0.88)

    # mean temp derived
    assert row[C.TMEAN] == pytest.approx((24.9 + 10.7) / 2.0)


def test_realistic_summer_et0():
    df = read_silo_fao56(FIXTURE)
    
    # Mildura January: hot, high evaporative demand.
    assert 4.0 < df[C.ET0].mean() < 9.0
    assert (df[C.TMAX] > df[C.TMIN]).all()


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        read_silo_fao56(FIXTURE.parent / "nope.txt")
