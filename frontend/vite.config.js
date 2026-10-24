import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": api,
      "/feedback": api,
      "/admin": api,
      "/health": api,
      "/me": api,
    },
  },
});
