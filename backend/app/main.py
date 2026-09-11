"""FastAPI app: serves the precomputed AquaReserve results to the dashboard

Every endpoint reads the store (and scenario config) - nothing runs the engine at request time.
The digital-twin viewers and, when built, the React dashboard are served as static files from the same app so the whole thing deploys as one service.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import (
    create_user,
    ensure_admin,
    get_current_user,
    make_token,
    public_user,
    require_admin,
    verify_password,
)
from .auth import find_user_by_email as _find_user_by_email
from .schemas import (
    AuthResponse,
    ComparisonRow,
    ConfigureRequest,
    ConfigureResponse,
    DemoDecideRequest,
    DemoDecision,
    LeadRequest,
    LeadSaved,
    LoginRequest,
    Meta,
    RegisterRequest,
    RoiResponse,
)
from .store import REPO_ROOT, VIZ_DIR, StoreError, get_store

ensure_admin()  # seed the admin account from env if configured

app = FastAPI(
    title="AquaReserve Dashboard API",
    version=__version__,
    description="Read-only API over the precomputed simulation results (precompute and serve).",
)

# The dashboard is served from the same origin in production; CORS stays open so the frontend dev server (Vite on :5173) can call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    try:
        store = get_store()
        return {"status": "ok", "version": __version__, "rows": len(store.rows)}
    except StoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/meta", response_model=Meta)
def meta() -> dict[str, object]:
    return get_store().meta()


@app.get("/api/matrix", response_model=list[dict])
def matrix(
    year: str | None = Query(None),
    controller: str | None = Query(None),
    reserve_ml: float | None = Query(None),
) -> list[dict]:
    return get_store().matrix(year=year, controller=controller, reserve_ml=reserve_ml)


@app.get("/api/comparison", response_model=list[ComparisonRow])
def comparison(
    year: str = Query(..., description="climate scenario, e.g. 'normal' or 'severe'"),
    reserve_ml: float = Query(20.0),
) -> list[dict]:
    try:
        return get_store().comparison(year=year, reserve_ml=reserve_ml)
    except StoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/reserve-sweep", response_model=list[dict])
def reserve_sweep(
    controller: str = Query(...),
    year: str = Query(...),
) -> list[dict]:
    try:
        return get_store().reserve_sweep(controller=controller, year=year)
    except StoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/roi", response_model=RoiResponse)
def roi(reserve_ml: float = Query(20.0)) -> dict:
    return get_store().roi(reserve_ml=reserve_ml)


# -- Auth -------------------------------------------------------
@app.post("/api/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> dict:
    try:
        user = create_user(req.email, req.password, req.name, req.farm, role="customer")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"token": make_token(user), "user": public_user(user)}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest) -> dict:
    user = _find_user_by_email(req.email)
    if not user or not verify_password(user, req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": make_token(user), "user": public_user(user)}


@app.get("/api/auth/me")
def me(user: Any = Depends(get_current_user)) -> dict:
    return public_user(user)


@app.post("/api/configure", response_model=ConfigureResponse)
def configure(req: ConfigureRequest, user: Any = Depends(get_current_user)) -> dict:
    """Size a system, estimate the outcome and price it for a farm profile.

    Runs the validated engine, so it is slower than the read endpoints.
    Imported lazily so the modeling core loads only when this route is called.
    Requires a signed-in user.
    """
    from aquareserve.configurator import FarmProfile, ZoneInput
    from aquareserve.configurator import configure as run_configure

    try:
        profile = FarmProfile(
            zones=[ZoneInput(z.crop, z.area_ha, z.irrigation) for z in req.zones],
            region=req.region,
            existing_reserve_ml=req.existing_reserve_ml,
            has_pump=req.has_pump,
            price_scale=req.price_scale,
            discount_rate=req.discount_rate,
            severe_year_probability=req.severe_year_probability,
            licence_cap_ml=req.licence_cap_ml,
        )
        return run_configure(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/proposal")
def proposal(req: ConfigureRequest, user: Any = Depends(get_current_user)) -> Response:
    """Generate a one-page system proposal PDF for a farm profile."""
    from aquareserve.configurator import FarmProfile, ZoneInput
    from aquareserve.configurator import configure as run_configure

    from .proposal import build_proposal_pdf

    try:
        profile = FarmProfile(
            zones=[ZoneInput(z.crop, z.area_ha, z.irrigation) for z in req.zones],
            region=req.region,
            existing_reserve_ml=req.existing_reserve_ml,
            has_pump=req.has_pump,
            price_scale=req.price_scale,
            licence_cap_ml=req.licence_cap_ml,
        )
        result = run_configure(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pdf = build_proposal_pdf(req.model_dump(), result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=aquareserve-proposal.pdf"},
    )


@app.post("/api/leads", response_model=LeadSaved)
def save_lead_endpoint(req: LeadRequest, user: Any = Depends(get_current_user)) -> dict:
    """Save a configuration and contact for follow-up, tied to the signed-in user."""
    from .leads import save_lead

    record = {
        "user": {"id": user["id"], "email": user["email"]},
        "contact": req.contact.model_dump(),
        "profile": {
            "region": req.region,
            "zones": [z.model_dump() for z in req.zones],
            "existing_reserve_ml": req.existing_reserve_ml,
            "has_pump": req.has_pump,
        },
        "summary": req.summary,
    }
    return save_lead(record)


@app.get("/api/leads/mine")
def my_leads(user: Any = Depends(get_current_user)) -> list[dict]:
    """The signed-in user's own saved quotes."""
    from .leads import list_leads

    return [ld for ld in list_leads() if ld.get("user", {}).get("id") == user["id"]]


@app.get("/api/admin/leads")
def admin_leads(_admin: Any = Depends(require_admin)) -> list[dict]:
    """All saved leads, for the admin."""
    from .leads import list_leads

    return list_leads()


@app.post("/api/demo/decide", response_model=DemoDecision)
def demo_decide(req: DemoDecideRequest, user: Any = Depends(get_current_user)) -> dict:
    """Drive the live Monitor demo.
    Stateless: the caller owns the reserve level and passes it in, so the same endpoint serves many users at once with no session.
    Runs the same threshold + critical-stage + finite-reserve logic family as the deployable controllers.
    """
    from .demo import decide

    d = decide(
        moisture_pct=req.moisture_pct,
        reserve_ml=req.reserve_ml,
        critical_stage=req.critical_stage,
        initial_reserve_ml=req.initial_reserve_ml,
    )
    return d.__dict__


@app.get("/api/twin")
def twin() -> FileResponse:
    """The per-day playback data both digital-twin viewers replay."""
    path = get_store().twin_data_path()
    if path is None:
        raise HTTPException(
            status_code=404,
            detail="twin_data.json not found. Run 'python scripts/export_twin.py --json'.",
        )
    return FileResponse(path, media_type="application/json")


# -- static assets ------------------------------------------------------------
# The two digital-twin viewers (2D + 3D) ship as self-contained HTML.
if VIZ_DIR.exists():
    app.mount("/twins", StaticFiles(directory=str(VIZ_DIR), html=True), name="twins")

# The customer product app (the configurator) is served under /product.
# It is a separate build/app and can move to its own service later.
# Mounted before the root so it wins.
_PRODUCT_DIST = REPO_ROOT / "product" / "dist"
if _PRODUCT_DIST.exists():
    app.mount("/product", StaticFiles(directory=str(_PRODUCT_DIST), html=True), name="product")

# The built React dashboard (frontend/dist) is served at the root when present, so the whole app is a single deploy.
# Absent in dev - the Vite dev server serves the UI then.
_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
