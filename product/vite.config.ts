import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The product app is served under /product by the same FastAPI backend as the dashboard (it can be split to its own service later). 
// Base makes the built asset URLs resolve under that path. 
// In development, /api and /twins are proxied to the local backend on :8000.
export default defineConfig({
  base: "/product/",
  plugins: [react()],
  server: {
    port: 5174,
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
