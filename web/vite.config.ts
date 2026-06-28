import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, forward the API surface to the FastAPI app on :8000 so the browser
// talks to same-origin URLs (no CORS) and the bearer token flows straight through.
const API_TARGET = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/search': API_TARGET,
      '/ingest': API_TARGET,
      '/ingest/manifest': API_TARGET,
      '/documents': API_TARGET,
      '/healthz': API_TARGET,
      '/status': API_TARGET,
      '/settings': API_TARGET,
      '/docs': API_TARGET,
      '/openapi.json': API_TARGET,
    },
  },
})
