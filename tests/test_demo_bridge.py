"""Tests for the tabletop-demo bridge (scripts/demo_bridge.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

# noqa: E402
from fastapi.testclient import TestClient  


def _load_bridge():
    spec = importlib.util.spec_from_file_location("demo_bridge", REPO_ROOT / "scripts" / "demo_bridge.py")
    mod = importlib.util.module_from_spec(spec)

    assert spec and spec.loader

    # so dataclasses can resolve string annotations
    sys.modules[spec.name] = mod  
    spec.loader.exec_module(mod)

    return mod


@pytest.fixture()
def client() -> TestClient:
    mod = _load_bridge()

    c = TestClient(mod.app)
    c.post("/demo/reset", json={"zone": "tray-1", "initial_ml": 100})

    return c


def test_waters_when_dry_and_spends_reserve(client: TestClient) -> None:
    r = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 10})

    assert r.status_code == 200

    d = r.json()

    assert d["pump_ms"] > 0

    # the reserve was spent
    assert d["reserve_ml_after"] < 100  


def test_no_water_when_moist(client: TestClient) -> None:
    d = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 80}).json()

    assert d["pump_ms"] == 0
    assert "moist" in d["reason"]


def test_critical_stage_raises_the_trigger(client: TestClient) -> None:
    # moisture 40 sits between the normal (35) and critical (45) triggers
    normal = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 40}).json()

    assert normal["pump_ms"] == 0

    crit = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 40, "critical_stage": True}).json()

    assert crit["pump_ms"] > 0


def test_reserve_exhausts_and_watering_stops(client: TestClient) -> None:
    client.post("/demo/reset", json={"zone": "tray-1", "initial_ml": 20})
    reasons = []

    for _ in range(20):
        d = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 5}).json()
        reasons.append(d["reason"])

        if d["pump_ms"] == 0:
            break

    final = client.post("/demo/decide", json={"zone": "tray-1", "moisture_pct": 5}).json()
    
    assert final["pump_ms"] == 0
    assert "exhausted" in final["reason"]
    assert final["reserve_pct"] == 0.0
