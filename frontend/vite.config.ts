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
  build: {
    rollupOptions: {
      output: {
        // Split big third-party libs into their own chunks so they load in
        // parallel and stay cached across app-code deploys. (react-markdown is
        // intentionally NOT listed — it's dynamically imported via Markdown.tsx
        // and gets its own lazy chunk.)
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-dnd": ["@dnd-kit/core", "@dnd-kit/sortable", "@dnd-kit/utilities"],
          "vendor-motion": ["framer-motion"],
        },
      },
    },
  },
});
