import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/investigate": "http://localhost:8002",
      "/investigations": "http://localhost:8002",
      "/slack": "http://localhost:8002",
      "/health": "http://localhost:8002",
    },
  },
})
