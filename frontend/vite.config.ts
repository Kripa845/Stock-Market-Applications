import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server runs on 5173 to match Backend/config/settings.py
// FRONTEND_URL / CORS_ALLOWED_ORIGINS default of http://localhost:5173
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
