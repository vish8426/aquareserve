"""Tests for the dashboard backend (Phase 7, F1).

These exercise the read-and-serve API against the real precomputed store when it is present.
If the store has not been generated (``python scripts/run_matrix.py``), the whole module is skipped rather than failing, since the store is regenerable and gitignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from backend.app.store import StoreError, get_store  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _store_available() -> bool:
    try:
        get_store.cache_clear()
        get_store()

        return True

    except StoreError:
        return False


pytestmark = pytest.mark.skipif(
    not _store_available(),

    reason="results store not generated (run scripts/run_matrix.py)",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    from backend.app.main import app

    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")

    assert r.status_code == 200

    body = r.json()

    assert body["status"] == "ok"
    assert body["rows"] > 0


def test_meta_shape(client: TestClient) -> None:
    r = client.get("/api/meta")

    assert r.status_code == 200

    m = r.json()

    assert m["reserve_capacity_ml"] == pytest.approx(20.0)

    ids = {z["crop"] for z in m["zones"]}

    assert {"onion", "wheat", "barley"} <= ids

    # onion is the drip horticulture zone
    assert any(z["crop"] == "onion" and z["horticulture"] for z in m["zones"])

    controllers = {c["id"] for c in m["controllers"]}

    assert {"rainfed", "mpc", "oracle"} <= controllers
    assert {y["id"] for y in m["years"]} >= {"normal", "severe"}


def test_comparison_ranked_and_saves_crops(client: TestClient) -> None:
    r = client.get("/api/comparison", params={"year": "severe", "reserve_ml": 20})

    assert r.status_code == 200

    rows = r.json()

    # sorted by production, descending
    prod = [row["production_t"] for row in rows]

    assert prod == sorted(prod, reverse=True)

    # a controller beats rainfed under drought (proves the system protects yield)
    rainfed = next(row for row in rows if row["controller"] == "rainfed")
    best = rows[0]

    assert best["controller"] != "rainfed"
    assert best["production_t"] > rainfed["production_t"]
    assert best["saved_t"] > 0


def test_reserve_sweep_monotone_context(client: TestClient) -> None:
    r = client.get("/api/reserve-sweep", params={"controller": "mpc", "year": "severe"})

    assert r.status_code == 200

    rows = r.json()
    caps = [row["reserve_ml"] for row in rows]

    assert caps == sorted(caps)

    # more storage never produces less under drought
    prod = [row["production_t"] for row in rows]

    assert prod[-1] >= prod[0]


def test_roi_payback_and_npv(client: TestClient) -> None:
    r = client.get("/api/roi", params={"reserve_ml": 20})

    assert r.status_code == 200

    roi = r.json()

    assert roi["capex"] > 0

    mpc = next(c for c in roi["controllers"] if c["controller"] == "mpc")

    assert mpc["payback_years"] is not None and mpc["payback_years"] > 0
    assert mpc["npv"] > 0


def test_matrix_filters(client: TestClient) -> None:
    r = client.get("/api/matrix", params={"year": "normal", "controller": "mpc"})

    assert r.status_code == 200

    rows = r.json()

    assert rows and all(row["year"] == "normal" and row["controller"] == "mpc" for row in rows)


@pytest.fixture()
def auth(client: TestClient, tmp_path, monkeypatch) -> dict:
    """Register a fresh customer against a temp user store and return auth headers."""
    import backend.app.auth as authmod

    monkeypatch.setattr(authmod, "USERS_PATH", tmp_path / "users.jsonl")

    r = client.post(
        "/api/auth/register",
        json={"email": "grower@example.com", "password": "password123", "name": "Grower"},
    )

    assert r.status_code == 200, r.text

    return {"headers": {"Authorization": f"Bearer {r.json()['token']}"}}


def test_configure_requires_auth(client: TestClient) -> None:
    r = client.post("/api/configure", json={"zones": [{"crop": "onion", "area_ha": 4}]})

    assert r.status_code == 401


def test_configure_endpoint(client: TestClient, auth: dict) -> None:
    # existing reserve -> the fast path (no sizing sweep) keeps the test quick
    body = {
        "zones": [
            {"crop": "onion", "area_ha": 4, "irrigation": "drip"},
            {"crop": "wheat", "area_ha": 12},
            {"crop": "barley", "area_ha": 8},
        ],
        "existing_reserve_ml": 20,
        "has_pump": True,
    }

    r = client.post("/api/configure", json=body, headers=auth["headers"])

    assert r.status_code == 200

    d = r.json()

    assert d["design"]["reserve_ml"] == 20
    assert d["design"]["build_storage"] is False
    assert d["design"]["capex_aud"] == pytest.approx(26000.0)
    assert d["economics"]["payback_years"] > 0 and d["economics"]["npv_aud"] > 0
    assert d["outcome"]["production_t"] > d["outcome"]["rainfed_t"]
    assert d["outcome"]["crops"]["onion"]["marketable"] is True


def test_configure_licence_cap_flows_through(client: TestClient, auth: dict) -> None:
    # fast path (existing reserve) with a licence below it: endpoint returns the licence note
    body = {
        "zones": [{"crop": "onion", "area_ha": 4, "irrigation": "drip"}, {"crop": "wheat", "area_ha": 12}],
        "existing_reserve_ml": 20,
        "has_pump": True,
        "licence_cap_ml": 15,
    }

    r = client.post("/api/configure", json=body, headers=auth["headers"])

    assert r.status_code == 200

    d = r.json()

    assert d["design"]["licence_cap_ml"] == 15
    assert d["licence"]["cap_ml"] == 15
    assert "exceeds" in (d["licence"]["note"] or "")


def test_configure_rejects_unknown_crop(client: TestClient, auth: dict) -> None:
    r = client.post("/api/configure", json={"zones": [{"crop": "dragonfruit", "area_ha": 2}]}, headers=auth["headers"])

    assert r.status_code == 422


def test_proposal_returns_pdf(client: TestClient, auth: dict) -> None:
    body = {
        "zones": [{"crop": "onion", "area_ha": 4, "irrigation": "drip"}, {"crop": "wheat", "area_ha": 12}],
        "existing_reserve_ml": 20,
        "has_pump": True,
    }

    r = client.post("/api/proposal", json=body, headers=auth["headers"])

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

    # a real document
    assert len(r.content) > 800


def test_leads_save_and_list_mine(client: TestClient, auth: dict, tmp_path, monkeypatch) -> None:
    import backend.app.leads as leads

    monkeypatch.setattr(leads, "LEADS_PATH", tmp_path / "leads.jsonl")
    body = {
        "zones": [{"crop": "onion", "area_ha": 4, "irrigation": "drip"}],
        "existing_reserve_ml": 20,
        "has_pump": True,
        "contact": {"name": "Test Grower", "email": "grower@example.com", "farm": "Test Farm"},
        "summary": {"capex_aud": 118000, "payback_years": 1.8},
    }

    r = client.post("/api/leads", json=body, headers=auth["headers"])

    assert r.status_code == 200

    lead_id = r.json()["id"]

    assert lead_id

    mine = client.get("/api/leads/mine", headers=auth["headers"]).json()

    match = next((x for x in mine if x["id"] == lead_id), None)

    assert match is not None
    assert match["summary"]["capex_aud"] == 118000
    assert match["user"]["email"] == "grower@example.com"


def test_demo_decide_requires_auth(client: TestClient) -> None:
    r = client.post("/api/demo/decide", json={"moisture_pct": 20, "reserve_ml": 400})

    assert r.status_code == 401


def test_demo_decide_waters_when_dry_and_stops_when_empty(client: TestClient, auth: dict) -> None:
    # dry soil with reserve available -> the pump runs and the reserve falls
    dry = client.post(
        "/api/demo/decide",
        json={"moisture_pct": 20, "reserve_ml": 400, "initial_reserve_ml": 400},
        headers=auth["headers"],
    ).json()

    assert dry["watered"] is True and dry["pump_ms"] > 0
    assert dry["reserve_ml_after"] < 400

    # moist soil -> no watering
    wet = client.post(
        "/api/demo/decide",
        json={"moisture_pct": 80, "reserve_ml": 400, "initial_reserve_ml": 400},
        headers=auth["headers"],
    ).json()

    assert wet["watered"] is False and wet["pump_ms"] == 0

    # empty reserve -> the crop is left unprotected even though it is dry
    empty = client.post(
        "/api/demo/decide",
        json={"moisture_pct": 20, "reserve_ml": 0, "initial_reserve_ml": 400},
        headers=auth["headers"],
    ).json()

    assert empty["watered"] is False and empty["reserve_pct"] == 0.0
    assert "exhausted" in empty["reason"]

    # the critical-stage trigger is higher so soil that was fine now gets watered
    normal = client.post(
        "/api/demo/decide",
        json={"moisture_pct": 40, "reserve_ml": 400, "critical_stage": False},
        headers=auth["headers"],
    ).json()

    critical = client.post(
        "/api/demo/decide",
        json={"moisture_pct": 40, "reserve_ml": 400, "critical_stage": True},
        headers=auth["headers"],
    ).json()

    assert normal["watered"] is False and critical["watered"] is True


def test_login_and_me(client: TestClient, tmp_path, monkeypatch) -> None:
    import backend.app.auth as authmod

    monkeypatch.setattr(authmod, "USERS_PATH", tmp_path / "users.jsonl")
    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123", "name": "A"})
    bad = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})

    assert bad.status_code == 401

    good = client.post("/api/auth/login", json={"email": "a@b.com", "password": "password123"})

    assert good.status_code == 200

    token = good.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com" and me.json()["role"] == "customer"


def test_register_requires_name(client: TestClient, tmp_path, monkeypatch) -> None:
    import backend.app.auth as authmod

    monkeypatch.setattr(authmod, "USERS_PATH", tmp_path / "users.jsonl")
    r = client.post("/api/auth/register", json={"email": "n@e.com", "password": "password123", "name": "  "})

    assert r.status_code == 409
    assert "name" in r.json()["detail"].lower()


def test_admin_only_leads(client: TestClient, tmp_path, monkeypatch) -> None:
    import backend.app.auth as authmod

    monkeypatch.setattr(authmod, "USERS_PATH", tmp_path / "users.jsonl")
    authmod.create_user("admin@aquareserve.au", "adminpass123", name="Admin", role="admin")
    admin = client.post("/api/auth/login", json={"email": "admin@aquareserve.au", "password": "adminpass123"})
    admin_h = {"Authorization": f"Bearer {admin.json()['token']}"}
    cust = client.post("/api/auth/register", json={"email": "c@e.com", "password": "password123", "name": "C"})
    cust_h = {"Authorization": f"Bearer {cust.json()['token']}"}

    assert client.get("/api/admin/leads", headers=admin_h).status_code == 200
    assert client.get("/api/admin/leads", headers=cust_h).status_code == 403
    assert client.get("/api/admin/leads").status_code == 401
