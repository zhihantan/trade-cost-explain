import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Root is this folder (`vite build frontend`); output goes to frontend/dist, served by FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" }, // dev proxy: /api -> FastAPI
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
});
