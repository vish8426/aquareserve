# AquaReserve - Project Plan
**Project:** Smart Supplementary Irrigation Digital Twin
**Programme:** MSSE Capstone Project, Quantic School of Business and Technology
**Owner / Product Owner / Scrum Master:** Vishant P
**Document Status:** Living Document - Updated each Sprint Planning Meeting.

## 1. Vision & Problem Statement
Drought and erratic rainfall threaten crop yield. A finite backup water reserve (harvested rainwater + farm dam/bore) can protect crops *if released intelligently*. AquaReserve is a software-controlled supplementary irrigation system, delivered as a **closed-loop simulation (digital twin)**, that schedules a limited reserve across crop zones and growth stages - under forecast uncertainty - to **minimise yield loss per cubic metre of water**.

The engineering core is a constrained optimisation problem. The product wraps it in a monitoring + simulation-playback dashboard and a cost/ROI model that tells a farmer whether the system pays for itself.

> **Scope Guardrail:** The hardware layer (sensors, valves, pump, edge controller, LoRaWAN/MQTT comms) is *modeled* inside the twin with optional fidelity (noise, drift, latency).

## 2. Goals & Success Criteria
| #   | Goal                                        | Measure of success                                                                                                                |
|---  |------                                       |--------------------                                                                                                               |
| G1  | Faithful closed-loop crop-water simulation  | FAO-56 ET, soil-water balance and yield response reproduce textbook behaviour on sanity scenarios                                 |
| G2  | Demonstrable benefit of smart control       | Smart controller preserves **X%** more yield / saves **Y%** more water vs baselines under drought (target quantified in results)  |
| G3  | Control under uncertainty                   | EKF root-zone estimator reduces state error vs raw noisy sensors                                                                  |
| G4  | Economic case                               | Cost/ROI model produces payback period + NPV with sensitivity to crop price & drought severity                                    |
| G5  | Working, deployed product                   | React dashboard deployed to a free tier; reproducible runs; documented + tested code                                              |

## 3. Team & Roles
This was a solo project. <br>
All Scrum roles are held by the owner, but they are kept *distinct in practice* to exercise the methodology:
- **Product Owner** - Owns the backlog, prioritisation, acceptance of user stories.
- **Scrum Master** - Runs sprint planning/review/retro, maintains the board, guards CI.
- **Developer / Code Owner** - Implements, reviews own PRs against a checklist, merges.

> Even solo, every change lands via a pull request with green CI before merge to `main`, so the workflow mirrors a team and produces an auditable history.

## 4. Engineering Methodology
- **Process:** Scrum with fixed-length sprints (suggested 2 weeks). Minimum **3 sprints** per the project prompt handbook; this plan uses **4** to comfortably cover the advanced controller and product polish.
- **Branching:** Trunk-based with short-lived feature branches → PR → squash-merge to `main`. `develop` optional for integration.
- **CI/CD:** GitHub Actions on every push/PR - lint (ruff), config validation and pytest with coverage across Python 3.10-3.12 (`.github/workflows/ci.yml`). Dashboard auto-deploys to a free tier (Render/Railway) from `main`.
- **Definition of Done:** see §8.

## 5. Tooling
| Concern             | Tool                                                                                                                                                | Notes                                                                                       |
|---                  |---                                                                                                                                                  |---                                                                                          |
| Source Control      | GitHub (shared with `quantic-grader`)                                                                                                               | public repo                                                                                 |
| Task Board          | GitHub Projects (Scrum board) or Trello                                                                                                             | links from README + submission                                                              |
| CI                  | GitHub Actions                                                                                                                                      | lint + validate + test + coverage                                                           |
| Hosting (Web App)   | Render (free tier), single service                                                                                                                  | FastAPI serves the built React app + API                                                    |
| Language / Sim      | Python 3.11+ (NumPy, SciPy, pandas)                                                                                                                 | src-layout package                                                                          |
| Crop-Water Engine   | own transparent FAO-56/FAO-33 engine                                                                                                                | control-oriented state equations                                                            |
| Model Validation    | pyfao56 + AquaCrop-OSPy                                                                                                                             | independent cross-checks of the engine                                                      |
| Estimation          | custom EKF, then EnKF                                                                                                                               | fuse noisy sensors with the soil-water model                                                |
| Control             | receding-horizon LP via scipy.optimize.linprog/HiGHS (MPC, robust MPC, oracle); Cross-Entropy Method in NumPy for RL (optional Gymnasium + SB3 PPO) | convex + CI-safe MPC, perfect-foresight bound, reproducible AI policy (see ADR-010/011/012) |
| Forecasting         | empirical ensemble resampling (NumPy)                                                                                                               | probabilistic forecast → robust quantile MPC                                                |
| Results Store       | Parquet + DuckDB                                                                                                                                    | precompute and serve; analytical queries                                                    |
| Backend / Frontend  | FastAPI; Vite + React + TypeScript + Apache ECharts                                                                                                 | ECharts for scientific time-series playback                                                 |
| Quality             | pytest, pytest-cov, ruff, mypy; vitest (frontend)                                                                                                   |                                                                                             |

## 6. Phase → Sprint Roadmap
> **Delivery Status:** All phases are delivered across the four sprints:
> - The transparent engine and validation
> - The full controller ladder (baselines, smart rule, MPC, robust MPC, oracle, RL), 
> - The EKF and EnKF, 
> - The cost/ROI model, 
> - The precompute and serve backend,
> - The React results dashboard with the 2D/3D twins,
> - The Docker/Render deploy and CI,
> - The customer product app (configurator, proposal, save-a-quote, auth and a live Monitor demo) and
> - The study.

**Delivery Philosophy: MVP-First, Advanced Methods Layered as Committed Additions:** 
The strategy (chosen with the Product Owner) is *Balanced* - get a fully working, deployed system standing early (the MVP), then add the advanced methods on top so each is a clean, independently-demoable increment rather than a delivery risk.

- **MVP (must Fully Work & Deploy):** The transparent engine, baselines + smart rule-based controller + **EKF**, **MPC**, ROI model and the deployed dashboard.
- **Committed Advanced Additions (Layered after MVP):** Engine **validation** vs pyfao56/AquaCrop, **EnKF** estimator, **perfect-foresight oracle** bound, probabilistic **forecasting → stochastic MPC** and an **RL** comparison policy.

| Phase   | Description                                                                                         | Sprint        |
|---      |---                                                                                                  |---            |
| **0**   | Repo scaffold; config schema (farm, crops, climate, reserve).                                       | **Sprint 1**  |
| **1**   | Weather loader + drought injection; FAO-56 Penman-Monteith ET; soil-water balance.                  | **Sprint 1**  |
| **2**   | Crop demand/stress (Kc, Ks); FAO-33 yield (Ky); reserve dynamics.                                   | **Sprint 2**  |
| **2b**  | **Engine validation** vs pyfao56 & AquaCrop-OSPy (verification story).                              | **Sprint 2**  |
| **3**   | Baseline controllers (rainfed/fixed/threshold) + metrics harness.                                   | **Sprint 2**  |
| **4**   | Smart rule-based critical-stage controller; **EKF** root-zone estimator.                            | **Sprint 3**  |
| **4b**  | **EnKF** estimator (SOTA data assimilation) + EKF-vs-EnKF comparison.                               | **Sprint 3**  |
| **5**   | **MPC** controller (receding-horizon LP, scipy/HiGHS); **perfect-foresight oracle** upper bound.    | **Sprint 3**  |
| **5b**  | Probabilistic **forecasting** → **stochastic MPC**; **RL** policy (Gymnasium+SB3).                  | **Sprint 4**  |
| **6**   | Cost / ROI model (BOM, capex/opex, payback, NPV, sensitivity).                                      | **Sprint 3**  |
| **7**   | Precompute experiment runner → Parquet/DuckDB; FastAPI API; React/TS + ECharts dashboard; deploy.   | **Sprint 4**  |
| **8**   | Full comparison study, sensitivity analysis, design/testing doc, demo recording.                    | **Sprint 4**  |

## 7. Sprint Plan
### Sprint 1 - Foundation & Core Engine *(Weeks 1-2)*
**Goal:** A validated scenario can be loaded and stepped through weather + soil water. 
- Phase 0: Scaffold, repo, config schema, CI, tests, docs. 
- Phase 1: SILO/BoM weather loader (+ deterministic synthetic fallback), drought-injection multipliers, FAO-56 Penman-Monteith ET₀, root-zone soil-water-balance engine.
- **Demo:** Load farm config, run one season of soil-water balance for a zone, plot soil moisture vs rainfall/ET.

### Sprint 2 - Crop Response, Reserve, Validation & Baselines *(weeks 3-4)*
**Goal:** A validated end-to-end closed loop with baseline controllers and metrics.
- Phase 2: Crop demand ET_c via Kc(stage) + stress Ks; FAO-33 yield response; finite reserve dynamics.
- Phase 2b: A validated engine against pyfao56 and AquaCrop-OSPy on shared scenarios; document agreement/differences (verification story for the design doc).
- Phase 3: Rainfed / fixed / threshold baseline controllers; metrics harness (relative yield, WUE, stress-days, reserve survival); first experiment runs.
- **Demo:** Engine-vs-reference validation plot; baselines across normal/moderate/severe drought.

### Sprint 3 - Smart Control, Estimation, MPC Oracle & Economics *(weeks 5-7)*
**Goal:** The headline contribution - smart control under uncertainty - plus the economic case.
- Phase 4: Rule-based critical-stage deficit controller; **EKF** root-zone estimator.
- Phase 4b: **EnKF** estimator; EKF-vs-EnKF estimation-error comparison.
- Phase 5: **MPC** controller (receding-horizon LP via scipy/HiGHS) over the reserve; **perfect-foresight oracle** as an upper-bound benchmark.
- Phase 6: Cost/ROI model (BOM, capex/opex, payback, NPV, sensitivity).
- **Demo:** Smart/EKF/MPC vs baselines vs oracle; payback chart.

### Sprint 4 - Advanced Control, Product, Deployment & Write-up *(weeks 8-10)*
**Goal:** The full method set, a deployed product and the final academic deliverables.
- Phase 5b: Probabilistic **forecasting** → **stochastic MPC**; **RL** comparison policy (Gymnasium + Stable-Baselines3).
- Phase 7: Precompute the experiment matrix → Parquet/DuckDB; FastAPI API; Vite + React + TypeScript + Apache ECharts dashboard (monitoring + season playback + controller comparison); deploy as a single Render service.
- Phase 8: Full comparison study & sensitivity analysis; finalise the design/testing doc; record the 15-20 min demo/presentation.
- **Demo:** The final, deployed system with the complete controller comparison.

## 8. Definition
A backlog item is **Done** when:
1. Code is implemented behind config (no hard-coded agronomic constants).
2. Unit/integration tests cover it and **all CI checks pass** (lint, validate, tests).
3. It is documented (docstrings + relevant doc/README update).
4. It is merged to `main` via a reviewed PR.
5. The Product Owner accepts it against its acceptance criteria.

## 9. Risk Register
| Risk                                                      | Likelihood  | Impact  | Mitigation                                                                          |
|---                                                        |---          |---      |---                                                                                  |
| Crop/ET Model Miscalibration Produces Implausible Yields  | Med         | High    | Sanity scenarios + cross-check against FAO references and AquaCrop where available  |
| MPC Tuning/Convergence                                    | Med         | Med     | Rule-based smart controller is the MVP; MPC is incremental on top                   |
| Climate Data Access/Format Friction (SILO/BoM)            | Low         | Med     | Loader abstracts source; synthetic-weather fallback for tests/CI                    |
| Scope Creep (RL, Hardware Fidelity)                       | Med         | Med     | RL & high-fidelity hardware are explicitly *stretch*                                |
| Solo Bandwidth                                            | Med         | High    | MVP-first phasing; each phase independently demoable                                |

## 10. Final Submission Checklist 
- [ ] GitHub repo shared with `quantic-grader`, well documented.
- [ ] Link to deployed dashboard (free tier) in the README.
- [ ] Public task board linked, showing user stories & tasks per sprint.
- [ ] `docs/DESIGN_AND_TESTING.md` complete (architecture decisions + testing).
- [ ] ≥ 3 sprints, each with a recorded demo to the Product Owner.
- [ ] CI/CD in active use (green badge).
- [ ] Final 15-20 min recorded demo/presentation (single mp4, ID shown on camera).
