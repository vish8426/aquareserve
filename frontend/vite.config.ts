import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dashboard calls the FastAPI backend at /api and embeds the twin viewers from /twins.
// In production both are served by the same FastAPI app (single deploy); in development we proxy them to the local uvicorn server so the frontend runs on Vite's :5173 dev server.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/twins": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
