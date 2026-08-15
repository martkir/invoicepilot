import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The real config with two ports moved, so a check can run beside whatever
// else is already bound on this machine.
export default defineConfig({
  root: __dirname,
  plugins: [react()],
  server: {
    port: 5199,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
