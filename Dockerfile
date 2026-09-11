# AquaReserve - single-image deploy.
# Stage 1 builds the React dashboard; 
# Stage 2 installs the Python core + API and precomputes the results store and twin data, then serves everything (API, built dashboard and the twin viewers) from one FastAPI process. 
# Precompute and serve: No simulation runs at request time.

# --- stage 1: build both frontends ------------------------------------------
FROM node:20-bookworm-slim AS frontend

# results dashboard (served at /)
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# customer product app (served at /product)
WORKDIR /app/product
COPY product/package.json product/package-lock.json ./
RUN npm ci
COPY product/ ./
RUN npm run build

# --- stage 2: python runtime ------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src
WORKDIR /app

# install the package with the API extra (fastapi, uvicorn, duckdb, pyarrow); the core scientific deps (numpy/scipy/pandas) come from the base dependencies as manylinux wheels
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[api]"

# application code and inputs
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY viz/ ./viz/
COPY backend/ ./backend/
COPY data/ ./data/

# built dashboard and product app from stage 1
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY --from=frontend /app/product/dist ./product/dist

# precompute the results store and the twin playback data at build time
RUN python scripts/run_matrix.py && python scripts/export_twin.py --json

EXPOSE 8000
# Render (and most hosts) inject $PORT; default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
