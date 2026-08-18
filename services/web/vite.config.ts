import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dashboard calls same-origin "/api/..." paths in both dev and production.
// In dev this proxy is what makes that true, which is why the backend needs no
// CORS configuration and the client needs no base-URL branching.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: { outDir: 'dist' },
})
