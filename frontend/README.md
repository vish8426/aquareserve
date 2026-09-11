# Frontend - React Dashboard
The deployable web app graders click through. 

Vite + React + TypeScript + Apache ECharts, styled as a corporate green theme with a landing page (a bundled Three.js 3D install hero). It reads the backend's precomputed API only (no simulation runs in the browser). This is the results dashboard, served at `/`; the separate customer product app (configurator plus the live Monitor demo) lives in `product/` and is served at `/product`.

## Tabs
- **Yield Protection** - controller comparison for a chosen season and reserve size, with a bar chart against the rainfed baseline and KPI cards for tonnes saved. This is the core "the system saves crops" evidence.
- **Reserve Sizing** - production vs reserve size (the diminishing-return / "software vs a bigger dam" curve).
- **Economics** - capex, expected annual benefit, payback and NPV per controller. 
- **Digital Twin** - embeds the 2D and 3D twin viewers the backend serves at `/twins`.

## Develop

```
cd frontend
npm install
npm run dev        # Vite on :5173, proxies /api and /twins to the backend on :8000
```

Run the backend alongside it (`uvicorn backend.app.main:app` from the repo root, after `python scripts/run_matrix.py` has generated the store).

## Build

```
npm run build      # type-checks then bundles to frontend/dist
```

In production `frontend/dist` is served by the same FastAPI app as the API and the twins, so the whole dashboard is a single deploy (see `render.yaml`).
