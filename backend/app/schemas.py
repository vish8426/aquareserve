"""Pydantic response models for the dashboard API

These type the JSON the frontend consumes.
Rows carry per-crop yield columns (``onion_t_ha`` and similar) that vary with the farm, so the row models allow extra fields rather than hard-coding every crop.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Zone(BaseModel):
    id: str
    crop: str
    area_ha: float
    irrigation_system: str
    horticulture: bool
    price_per_t: float


class ControllerInfo(BaseModel):
    id: str
    label: str
    deployable: bool


class YearInfo(BaseModel):
    id: str
    label: str


class Meta(BaseModel):
    farm: str
    region: str
    reserve_capacity_ml: float
    design_reserve_ml: float
    currency: str
    zones: list[Zone]
    controllers: list[ControllerInfo]
    years: list[YearInfo]
    reserve_sizes_ml: list[float]


class MatrixRow(BaseModel):
    model_config = ConfigDict(extra="allow")  # per-crop *_t_ha columns

    year: str
    controller: str
    reserve_ml: float
    production_t: float
    irrigation_ml: float
    survival_days: int
    value_aud: float
    rainfed_t: float
    saved_t: float
    saved_pct: float


class ComparisonRow(MatrixRow):
    label: str


class RoiEntry(BaseModel):
    controller: str
    label: str
    deployable: bool
    annual_benefit_normal: float
    annual_benefit_severe: float
    expected_annual_benefit: float
    payback_years: float | None
    npv: float


class RoiResponse(BaseModel):
    reserve_ml: float
    capex: float
    currency: str
    discount_rate: float
    horizon_years: int
    severe_year_probability: float
    controllers: list[RoiEntry]


# -- Configurator ------------------------------------------------
class ZoneInputModel(BaseModel):
    crop: str
    area_ha: float = Field(gt=0)
    irrigation: str | None = None


class ConfigureRequest(BaseModel):
    zones: list[ZoneInputModel]
    region: str = "mallee"
    existing_reserve_ml: float | None = None
    has_pump: bool = False
    price_scale: float = Field(1.0, gt=0)
    discount_rate: float | None = None
    severe_year_probability: float | None = None
    licence_cap_ml: float | None = Field(None, gt=0)  # water-licence / allocation cap 


class ConfigureResponse(BaseModel):
    design: dict
    outcome: dict
    economics: dict
    licence: dict | None = None  # water-licence cap outcome 


# -- Proposal and leads ------------------------------------------
class Contact(BaseModel):
    name: str
    email: str
    farm: str | None = None
    phone: str | None = None


class LeadRequest(ConfigureRequest):
    contact: Contact
    summary: dict | None = None  # design/economics highlights the client already computed


class LeadSaved(BaseModel):
    id: str
    created: str


# -- Live demo ---------------------------------
class DemoDecideRequest(BaseModel):
    moisture_pct: float = Field(ge=0, le=100)
    reserve_ml: float = Field(ge=0)
    initial_reserve_ml: float = Field(500.0, gt=0)
    critical_stage: bool = False


class DemoDecision(BaseModel):
    pump_ms: int
    watered: bool
    reason: str
    delivered_ml: float
    reserve_ml_after: float
    reserve_pct: float
    moisture_pct: float


# -- Auth -------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str
    password: str  # length is checked in create_user, which returns a friendly message
    name: str
    farm: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    role: str
    farm: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserOut
