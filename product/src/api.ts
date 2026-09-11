// Typed client for the AquaReserve backend.
// All data is precomputed and served read-only; the frontend never triggers a simulation run.

export interface Zone {
  id: string;
  crop: string;
  area_ha: number;
  irrigation_system: string;
  horticulture: boolean;
  price_per_t: number;
}

export interface ControllerInfo {
  id: string;
  label: string;
  deployable: boolean;
}

export interface YearInfo {
  id: string;
  label: string;
}

export interface Meta {
  farm: string;
  region: string;
  reserve_capacity_ml: number;
  design_reserve_ml: number;
  currency: string;
  zones: Zone[];
  controllers: ControllerInfo[];
  years: YearInfo[];
  reserve_sizes_ml: number[];
}

export interface MatrixRow {
  year: string;
  controller: string;
  reserve_ml: number;
  production_t: number;
  irrigation_ml: number;
  survival_days: number;
  value_aud: number;
  rainfed_t: number;
  saved_t: number;
  saved_pct: number;

  // per-crop yield columns, e.g. onion_t_ha, wheat_t_ha, barley_t_ha
  [key: string]: number | string;
}

export interface ComparisonRow extends MatrixRow {
  label: string;
}

export interface RoiEntry {
  controller: string;
  label: string;
  deployable: boolean;
  annual_benefit_normal: number;
  annual_benefit_severe: number;
  expected_annual_benefit: number;
  payback_years: number | null;
  npv: number;
}

export interface RoiResponse {
  reserve_ml: number;
  capex: number;
  currency: string;
  discount_rate: number;
  horizon_years: number;
  severe_year_probability: number;
  controllers: RoiEntry[];
}

// -- Configurator ------------------------------------------------
export interface ZoneProfile {
  crop: string;
  area_ha: number;
  irrigation?: string;
}

export interface ConfigureRequest {
  zones: ZoneProfile[];
  region?: string;
  existing_reserve_ml?: number | null;
  has_pump?: boolean;
  price_scale?: number;
  licence_cap_ml?: number | null;
}

export interface HardwareLine {
  item: string;
  type: string;
  qty: number;
  unit_cost: number;
  total: number;
}

export interface ConfigureResult {
  design: {
    reserve_ml: number;
    zones: number;
    build_storage: boolean;
    controller: string;
    hardware: HardwareLine[];
    capex_aud: number;
    reserve_basis?: string;
    reserve_sweep?: Record<string, { production_t: number; capex_aud: number; npv_aud: number; over_licence?: boolean }> | null;
    licence_cap_ml?: number | null;
    licence_capped?: boolean;
  };
  outcome: {
    production_t: number;
    rainfed_t: number;
    yield_protected_pct: number;
    water_used_ml: number;
    reserve_survival_days: number;
    crops: Record<string, { relative_yield: number; yield_t_ha: number; marketable: boolean; horticulture: boolean }>;
  };
  economics: {
    currency: string;
    capex_aud: number;
    expected_annual_benefit_aud: number;
    payback_years: number | null;
    payback_range_years: [number, number] | null;
    npv_aud: number;
    monthly_eaas_aud: number;
    discount_rate: number;
    severe_year_probability: number;
    horizon_years: number;
  };
  licence?: {
    cap_ml: number | null;
    capped: boolean;
    uncapped_reserve_ml?: number;
    forgone_production_t?: number;
    forgone_npv_aud?: number;
    note?: string | null;
  };
}

// -- Live demo (Monitor page) -------------------------------------------------
export interface DemoDecideRequest {
  moisture_pct: number;
  reserve_ml: number;
  initial_reserve_ml: number;
  critical_stage: boolean;
}

export interface DemoDecision {
  pump_ms: number;
  watered: boolean;
  reason: string;
  delivered_ml: number;
  reserve_ml_after: number;
  reserve_pct: number;
  moisture_pct: number;
}

// -- Auth token ---------------------------------------------------------
export interface User {
  id: string;
  email: string;
  name?: string;
  role: string;
  farm?: string;
}

let authToken: string | null = localStorage.getItem("aqua_token");

function setToken(t: string): void {

  authToken = t;
  localStorage.setItem("aqua_token", t);
}

function authHeaders(json = false): Record<string, string> {

  const h: Record<string, string> = {};

  if (json) h["Content-Type"] = "application/json";
  if (authToken) h["Authorization"] = `Bearer ${authToken}`;

  return h;
}

async function get<T>(path: string): Promise<T> {

  const res = await fetch(`/api${path}`, { headers: authHeaders() });

  if (!res.ok) {

    const detail = await res.text().catch(() => res.statusText);

    throw new Error(`${res.status} ${path}: ${detail}`);
  }

  return (await res.json()) as T;
}

// FastAPI returns `detail` as a string for our HTTPExceptions or an array of {loc, msg, type} objects for request-validation (422) errors.
// Render both readably.
function formatDetail(j: unknown, fallback: string): string {

  const d = (j as { detail?: unknown })?.detail;

  if (typeof d === "string") return d;
  if (Array.isArray(d)) {

    return d.map((e: { msg?: string }) => e?.msg ?? JSON.stringify(e)).join("; ");
  }

  return d ? JSON.stringify(d) : fallback;
}

async function post<T>(path: string, body: unknown): Promise<T> {

  const res = await fetch(`/api${path}`, {

    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  
  if (!res.ok) {

    let detail = res.statusText;

    try {

      detail = formatDetail(await res.json(), res.statusText);
    } catch {
      /*
       * keep statusText
      */
    }

    throw new Error(`${res.status}: ${detail}`);
  }

  return (await res.json()) as T;
}

export interface LeadContact {
  name: string;
  email: string;
  farm?: string;
  phone?: string;
}

async function postBlob(path: string, body: unknown): Promise<Blob> {

  const res = await fetch(`/api${path}`, {

    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });

  if (!res.ok) {

    let detail = res.statusText;

    try {

      detail = (await res.json()).detail ?? detail;
    } catch {
      /*
       * keep statusText
      */
    }

    throw new Error(`${res.status}: ${detail}`);
  }

  return res.blob();
}

export interface Lead {
  id: string;
  created: string;
  user?: { id: string; email: string };
  contact?: LeadContact;
  profile?: { region?: string; existing_reserve_ml?: number | null; has_pump?: boolean };
  summary?: Record<string, unknown>;
}

export const api = {
  meta: () => get<Meta>("/meta"),
  comparison: (year: string, reserveMl: number) => get<ComparisonRow[]>(`/comparison?year=${year}&reserve_ml=${reserveMl}`),
  reserveSweep: (controller: string, year: string) => get<MatrixRow[]>(`/reserve-sweep?controller=${controller}&year=${year}`),
  roi: (reserveMl: number) => get<RoiResponse>(`/roi?reserve_ml=${reserveMl}`),
  configure: (req: ConfigureRequest) => post<ConfigureResult>("/configure", req),
  demoDecide: (req: DemoDecideRequest) => post<DemoDecision>("/demo/decide", req),
  proposal: (req: ConfigureRequest) => postBlob("/proposal", req),
  saveLead: (payload: ConfigureRequest & { contact: LeadContact; summary?: Record<string, unknown> }) => post<{ id: string; created: string }>("/leads", payload),

  // auth
  register: async (p: { email: string; password: string; name: string; farm?: string }) => {
    const r = await post<{ token: string; user: User }>("/auth/register", p);

    setToken(r.token);

    return r.user;
  },

  login: async (p: { email: string; password: string }) => {
    const r = await post<{ token: string; user: User }>("/auth/login", p);

    setToken(r.token);

    return r.user;
  },
  me: () => get<User>("/auth/me"),
  
  logout: () => {
    authToken = null;
    localStorage.removeItem("aqua_token");
  },
  hasToken: () => Boolean(authToken),
  myLeads: () => get<Lead[]>("/leads/mine"),
  adminLeads: () => get<Lead[]>("/admin/leads"),
};
