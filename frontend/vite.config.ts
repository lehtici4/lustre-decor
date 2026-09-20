import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://backend:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: backendTarget, changeOrigin: false },
      // Django Admin (com MFA obrigatório) e o fluxo de login do django-two-factor-auth.
      // Encaminhados aqui para manter o backend sem porta própria publicada no host.
      '/admin': { target: backendTarget, changeOrigin: false },
      '/account': { target: backendTarget, changeOrigin: false },
      '/static': { target: backendTarget, changeOrigin: false },
    },
  },
})
