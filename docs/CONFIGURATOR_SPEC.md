# AquaReserve Configurator - Design Spec
The configurator is the bridge from the project to a sellable product. It takes a short farm profile and returns a sized system, an estimate of the yield protected and water saved and an indicative quote with payback. It reuses the existing engine, economics model and hardware BOM, so it is mostly assembly rather than new science.

It serves two roadmap stories from one tool:

- **Self-Serve Payback:** <br>
A prospect enters a few details on the public site and sees their own payback before any sales contact. <br>
Few inputs, sensible defaults, instant result.

- **Site Assessment & Design:** <br>
A salesperson or installer enters a fuller farm profile and gets a system design plus a quote and a proposal document to hand over. <br>
Same engine, richer inputs, exportable output.

> All costs and estimates are indicative for planning, not a firm quote. The tool/productisation is to disclose so.

## 1. Inputs
Kept minimal and others defaulted, expanded for sprint item E1. <br>
Defaults come from the example config so a prospect can get a number with almost no typing.

| Input                                           | D1            | E1              | Default / Source                                    |
|---                                              |---            |---              |---                                                  |
| Region / Nearest Town                           | Yes           | Yes             | Sets Climate (SILO Station); Mallee/Mildura at MVP  |
| Crop Zones: Crop, Area (ha), Irrigation Type    | Yes (Simple)  | Yes (per Zone)  | One-to-Three Zones; Onion/Wheat/Barley at MVP       |
| Existing Water Reserve? Size (ML)               | Yes           | Yes             | If Present, Storage Capex Drops toward Zero         |
| Existing Pump?                                  | No            | Yes             | Removes the Optional VFD Line                       |
| Water Licence / Allocation Cap (ML)             | No            | Yes             | Caps recommended Reserve Draw                       |
| Crop Prices, Discount Rate, Drought Probability | No (Defaults) | Yes (Editable)  | `config/economics.example.yaml`                     |

## 2. Sizing Logic (IP Surface)
This is the one genuinely new piece of logic. Everything downstream reuses existing modules.

- **Zones** = The number of independently controlled crop blocks the user entered.
- **Reserve Size** = A recommendation, not a free parameter. 

Estimate the supplementary volume needed to carry the highest-value crop through its critical growth stages in a design drought (sum over zones of the stage deficit in mm times area), then cross-check against the reserve-size sweep the study already produces: cap the recommendation where the marginal tonne per extra ML flattens (past ~20 ML for the model farm). 

Show the sweep curve so the user sees the diminishing return and can override.

- **Hardware** = Per-zone kit times zones, plus the central kit, plus install, plus a reserve build only if the user has no existing dam. 

Quantities and unit costs come straight from the BOM (`docs/AquaReserve-Hardware-BOM.xlsx`), which should be mirrored into a machine-readable `config/bom.yaml` so the sheet and the code share one source of truth.

## 3. Processing Pipeline

```
farm profile
   -> build a Scenario (reuse aquareserve.config.schema: Farm, Zone, Reserve, CropModel)
   -> size reserve + zones + hardware (new configurator module + config/bom.yaml)
   -> estimate outcome:
        precomputed grid lookup for common cases (fast, self-serve)   [precompute and serve]
        OR a bounded live engine run for a bespoke farm               [SimulationEngine.run]
        -> yield protected vs rainfed, water used, reserve survival, per-crop marketability
   -> economics (reuse aquareserve.metrics.economic):
        capex from the BOM, payback + NPV via evaluate(), sensitivity band from run_study logic
   -> assemble design + quote + proposal
```

The estimate step deliberately prefers the precompute and serve store for speed on the common Mallee cases and falls back to a single bounded engine run when the farm does not match the grid. Both already exist in the codebase.

## 4. Outputs
- **On Screen:** <br>
The recommended design (reserve size, zone count, hardware list), the estimated yield protected and water saved with the marketability uplift (for example onion moving from unmarketable to marketable), capex, payback, NPV and a monthly figure for the equipment-as-a-service option. <br>
Show the reserve-size sweep and a payback sensitivity band (reusing the study figures) so the number reads as a range, not false precision.

- **Downloadable Proposal:** <br> 
A one to two page PDF or Word document (reuse the pdf/docx tooling) with the design, the quote and the assumptions. <br>
This doubles as the E1 handover packet.

- **Saved Configuration:** <br>
A stored record (config in, design and quote out) for follow-up. <br>
At MVP this can be a row in the results store; it becomes a first-class object when the Phase C multi-tenant database lands.

## 5. Architecture (what to Build vs Reuse)
Reuse: the whole `aquareserve` engine, `metrics.economic` (`system_capex`, `evaluate`, `dam_capacity_to_match`), the config schema, the E2 store and the FastAPI plus React app.

Build:
- `src/aquareserve/configurator/` - a module that maps a farm profile to a Scenario, applies the sizing rules, pulls costs from `config/bom.yaml` and returns a typed design-plus-quote result.

- `config/bom.yaml` - the BOM (tiers, unit costs, per-zone and central kits) as data, kept in step with the spreadsheet.

- **Backend**: `POST /api/configure` (profile in, design and quote out) and `POST /api/proposal` (same input, returns the proposal document). Both sit alongside the existing read endpoints.

- **Frontend**: A "Configurator" wizard (a short form to a results page) added to the React app, reusing the ECharts comparison, reserve-sweep and ROI components already built, plus a "Download proposal" button.

Example Request & Response Shape:
```
POST /api/configure
{ "region": "mallee", "zones": [ {"crop":"onion","area_ha":4,"irrigation":"drip"},
                                 {"crop":"wheat","area_ha":12,"irrigation":"broadacre"} ],
  "existing_reserve_ml": 0, "has_pump": true }

-> { "design": { "reserve_ml": 20, "zones": 2, "hardware": [ ... ] },
     "outcome": { "yield_protected_pct": 308, "water_used_ml": 10.9,
                  "onion_marketable": true, "reserve_survival_days": 121 },
     "economics": { "capex_aud": 118000, "payback_years": 1.8, "npv_aud": 360000,
                    "monthly_eaas_aud": 1650, "payback_range": [1.5, 2.4] } }
```

## 6. MVP Scope vs Later
- **MVP:** <br>
  - single region (Mallee)
  - the three model crops
  - precomputed outcomes with a bounded live fallback
  - capex from `config/bom.yaml`
  - payback and NPV from the economics model
  - on-screen results plus a one-page proposal
  - public D1 form with defaults; 
    - a richer form behind a simple login.
    
- **Later:** <br>
  - more regions and crops (needs more SILO stations and calibration)
  - a live engine for fully bespoke farms
  - saved leads into a CRM and 
  - lease grant calculators
  
  The crop model is FAO-driven, so new crops are parameter packets, not code; the candidate list:
  - oilseeds
  - pulses
  - more cereals
  - horticulture
  - perennials as an extension is in `config/crops/README.md`

## 7. Acceptance Criteria
- D1: 
  - from the public form with defaults;
  - a prospect gets a design,
  - a capex figure and a payback range in one screen in under a few seconds,
  - with an indicative-only disclaimer

- E1: 
  - from the fuller form
  - a salesperson gets the same plus a downloadable proposal document and
  - a saved configuration record

- Every number traces to the engine, the BOM or the economics config; nothing is hardcoded in the UI. 

## 8. Candidate Stories (Board-Imported)
- **D1a** BOM mirrored into `config/bom.yaml` as the single cost source. 
- **D1b** `configurator` module: Farm profile to Scenario plus sizing rules, with unit tests.
- **D1c** `POST /api/configure` returning design, outcome and economics.
- **D1d** Configurator wizard and results page (now in the product app, `product/`).
- **D1e** Payback range and reserve-sweep shown as a band, not a single number.

- **E1a** The form has per-zone detail, existing reserve, pump and a water-licence cap. 
  - When a licence is given and the NPV-optimal reserve exceeds it, the recommendation is hard-capped at the licence and the forgone drought-year production is reported (option a); the reserve sweep marks sizes above the licence and the proposal PDF carries the note.

- **E1b**  `POST /api/proposal` builds a one-page PDF (`backend/app/proposal.py`, fpdf2); the product app has a Download proposal button.

- **E1c** (MVP) `POST /api/leads` saves a configuration plus contact tied to the signed-in user; `GET /api/leads/mine` lists the user's own quotes and `GET /api/admin/leads` lets the admin see all (`backend/app/leads.py`, JSONL); the product app has a Save this quote form. 
  - Flat-file for now, but authenticated via the E1d gate.

- **E1d** (MVP) Auth gate for the product app: Customer accounts (self-register/login) plus an admin account. 
  - Self-contained in the backend (`backend/app/auth.py`): File-based user store (`data/users.jsonl`), salted PBKDF2 hashing, HMAC-signed bearer tokens, all stdlib. 
  - The whole product app sits behind login; `/api/configure`, `/api/proposal` and `/api/leads` require a user; leads are tied to the user; `/api/leads/mine` and admin `/api/admin/leads` split the views. 
  - Admin is seeded from `AQUARESERVE_ADMIN_EMAIL` / `AQUARESERVE_ADMIN_PASSWORD`; set `AQUARESERVE_SECRET` in production. 
  - Graduates to a real user table (bcrypt/argon2, refresh tokens) with the Phase C database.

## 9. Risks & Assumptions
- The sizing rule is the main new logic and must be validated against pilot farms (roadmap A); until then, present recommendations as indicative with an easy override.
- Precomputed outcomes only cover the modeled region and crops; bespoke farms need the live engine path, which must stay bounded so the public endpoint cannot be overloaded.
- Costs are planning estimates from the BOM, not supplier quotes; the proposal must state this and a human should confirm an E1 quote before it goes to a customer.
