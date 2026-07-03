import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Read target API URL from system environment or default to local API server
const apiTarget = process.env.API_URL || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 8501,
    host: '0.0.0.0', // Allow connections from outside the container
    proxy: {
      '/health': apiTarget,
      '/act': apiTarget,
      '/request': apiTarget,
      '/audit': apiTarget,
      '/review': apiTarget,
      '/rules': apiTarget,
      '/patterns': apiTarget,
      '/agent': apiTarget,
    }
  }
})
