"""Tests for the experiment matrix runner."""

from aquareserve.config import load_scenario
from aquareserve.experiments import resize_reserve, run_matrix, write_results

CFG = "config/farm.example.yaml"


def test_resize_reserve_holds_fill_fraction():
    sc = load_scenario(CFG)
    frac = sc.farm.reserve.initial_volume_m3 / sc.farm.reserve.capacity_m3
    r = resize_reserve(sc, 10.0)

    assert r.farm.reserve.capacity_m3 == 10_000.0
    assert abs(r.farm.reserve.initial_volume_m3 / r.farm.reserve.capacity_m3 - frac) < 1e-9

    # original is untouched
    assert sc.farm.reserve.capacity_m3 != 10_000.0


def test_run_matrix_shape_and_columns():
    sc = load_scenario(CFG)

    ctrls = {"rainfed": lambda s, w, p: __import__(
        "aquareserve.controllers", fromlist=["RainfedController"]).RainfedController(),
        "threshold": lambda s, w, p: __import__(
        "aquareserve.controllers", fromlist=["ThresholdController"]).ThresholdController()}

    df = run_matrix(sc, years=["severe"], controllers=ctrls, reserve_sizes_ml=[10, 20], base_dir=".")

    # years x controllers x reserves
    assert len(df) == 1 * 2 * 2  

    for col in ["year", "controller", "reserve_ml", "production_t", "irrigation_ml", "survival_days", "value_aud", "rainfed_t", "saved_t", "saved_pct"]:
        assert col in df.columns

    assert (df["production_t"] > 0).all()

    # rainfed uses no reserve, so its production does not depend on reserve size
    rf = df[df["controller"] == "rainfed"].sort_values("reserve_ml")["production_t"].tolist()

    assert rf[0] == rf[1]


def test_bigger_reserve_helps_under_drought():
    sc = load_scenario(CFG)
    ctrls = {"threshold": lambda s, w, p: __import__("aquareserve.controllers", fromlist=["ThresholdController"]).ThresholdController()}
    df = run_matrix(sc, years=["severe"], controllers=ctrls,reserve_sizes_ml=[5, 30], base_dir=".")

    small = df[df["reserve_ml"] == 5.0]["production_t"].iloc[0]
    big = df[df["reserve_ml"] == 30.0]["production_t"].iloc[0]

    assert big >= small


def test_write_results_csv(tmp_path):
    sc = load_scenario(CFG)
    ctrls = {"rainfed": lambda s, w, p: __import__("aquareserve.controllers", fromlist=["RainfedController"]).RainfedController()}
    df = run_matrix(sc, years=["severe"], controllers=ctrls, reserve_sizes_ml=[20], base_dir=".")
    written = write_results(df, tmp_path)
    
    assert (tmp_path / "matrix.csv").exists()
    assert any(p.name == "matrix.csv" for p in written)
