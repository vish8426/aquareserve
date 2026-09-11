# Backend/ - FastAPI service

The read-and-serve API the dashboard talks to. It follows a **precompute and serve** architecture: the `aquareserve` core precomputes the scenario x controller x reserve-size results matrix once (`scripts/run_matrix.py`) and this service just queries that store. 

It runs **no** simulation at request time and holds **no** modeling logic of its own, so the deployed app is fast and stateless.

## Layout

```
backend/app/
  main.py      FastAPI app + routes + static serving of the twins, dashboard and product app.
  schemas.py   response models (Pydantic).
  store.py     read-only access to the E2 store (DuckDB/Parquet) + scenario config.
  auth.py      self-contained auth: PBKDF2 hashing, HMAC tokens, file-based user store.
  proposal.py  one-page proposal PDF via fpdf2.
  leads.py     save-a-quote store, JSONL.
  demo.py      stateless decision logic for the live Monitor demo.
```

The configurator, proposal and demo routes call the validated `aquareserve` core, so those few endpoints do run the engine lazily imported); the read-and-serve results endpoints never do.

## Endpoints

Read-and-serve (results dashboard):

- `GET /api/health` - store status and row count.
- `GET /api/meta` - farm, reserve, crops/zones, controllers, years, reserve sizes.
- `GET /api/matrix?year=&controller=&reserve_ml=` - the raw results matrix (filterable).
- `GET /api/comparison?year=&reserve_ml=` - controllers ranked by production for a season.
- `GET /api/reserve-sweep?controller=&year=` - production and survival vs reserve size.
- `GET /api/roi?reserve_ml=` - capex, expected annual benefit, payback and NPV per controller.
- `GET /api/twin` - the per-day playback data both digital-twin viewers replay.

Product app (auth-gated):

- `POST /api/auth/register` and `POST /api/auth/login` - customer accounts; `GET /api/auth/me`.
- `POST /api/configure` - farm profile to sized system, outcome and economics (configurator).
- `POST /api/proposal` - a one-page proposal PDF for a profile.
- `POST /api/leads`, `GET /api/leads/mine`, `GET /api/admin/leads` - save and list quotes.
- `POST /api/demo/decide` - one step of the live Monitor demo loop (stateless).

Static: `/twins/*` (2D and 3D twin viewers), `/product/*` (customer app), `/` (results dashboard).

## Run it

```
pip install -e ".[api,dev]"          # fastapi, uvicorn, duckdb, pyarrow
python scripts/run_matrix.py         # generate data/results/ first
uvicorn backend.app.main:app --reload
```

Then open http://127.0.0.1:8000/api/health and http://127.0.0.1:8000/docs.

The store location is resolved from the repo root by default and can be overridden with the `AQUARESERVE_ROOT`, `AQUARESERVE_DATA_DIR`, `AQUARESERVE_CONFIG_DIR` and `AQUARESERVE_VIZ_DIR` environment variables (used by the Render deploy).
