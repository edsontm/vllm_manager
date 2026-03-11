import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5177,
    allowedHosts: ['llm.liaufms.org', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://backend:8080',
        changeOrigin: true,
        headers: { 'X-Accel-Buffering': 'no' },
      },
      '/v1': {
        target: 'http://backend:8080',
        changeOrigin: true,
        headers: { 'X-Accel-Buffering': 'no' },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          charts: ['recharts'],
        },
      },
    },
  },
})
