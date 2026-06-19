import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend during development so the SPA and API share
// an origin (no CORS friction locally). In production the static build talks to
// the API via VITE_API_BASE.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on LAN so other devices can reach the dev server
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
