# Product/ - AquaReserve Customer Product App
The customer-facing product web-app, split from the results dashboard so the two evolve independently. It reads the same backend API. 

Pages: 
- a marketing **Home**, 
- the self-serve **Configure** tool (the configurator),
- a **Monitor** placeholder for the future live control and 
- monitoring product.

The results dashboard stays in `../frontend/` with its green presentation style.

## Develop

```
cd product
npm install
npm run dev        # Vite on :5174, proxies /api and /twins to the backend on :8000
```

Run the backend alongside it (`uvicorn backend.app.main:app` from the repo root).

## Build & Serve

```
npm run build      # type-checks then bundles to product/dist (base path /product/)
```

In production the backend serves this build at **`/product`** (the dashboard is at `/`). It can be split to its own deployable service later without code changes, since it only needs the API.

## Login & Admin 
The whole product app sits behind a login. Customers self-register; the product endpoints (`/api/configure`, `/api/proposal`, `/api/leads`) require a signed-in user, so saved quotes are tied to the account. Auth is self-contained in the backend (`backend/app/auth.py`) with a file-based user store and stdlib crypto - no external service or database server.

Backend Environment Variables:
- `AQUARESERVE_SECRET` - HMAC secret for signing tokens - **to be set this in production.**
- `AQUARESERVE_ADMIN_EMAIL` / `AQUARESERVE_ADMIN_PASSWORD` - seed an admin account on startup. The admin sees all saved quotes at the Admin tab; customers see only their own under My Quotes.

## Shared Code
`api.ts`, `format.ts`, `hooks.ts` and `components/Chart.tsx` and `components/Configurator.tsx` are copied from the dashboard for now. If the two apps keep sharing code, promote these into a small shared package. The theme lives in `src/styles.css` (from `docs/future/aero-theme.css`).
