import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../dashboard',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/chart.js') || id.includes('node_modules/react-chartjs-2')) {
            return 'vendor-charts'
          }
          if (id.includes('node_modules/@zxing')) {
            return 'vendor-qr'
          }
          if (id.includes('node_modules/lucide-react')) {
            return 'vendor-icons'
          }
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'vendor-react'
          }
          return undefined
        },
      },
    },
  },
})
