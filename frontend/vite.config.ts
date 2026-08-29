import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// El backend no publica puerto en el host: el dev server hace de proxy para
// que el navegador solo necesite hablar con el frontend (mismo origen).
const BACKEND_ORIGIN = process.env.VITE_BACKEND_ORIGIN ?? 'http://backend:8000'

// Vite 6 rechaza peticiones cuyo Host no reconoce (proteccion anti DNS
// rebinding). Las IP y localhost pasan siempre; los nombres de host (p. ej.
// "debianllama.local") hay que declararlos aqui o dan 403 "Blocked request".
// VITE_ALLOWED_HOSTS admite una lista separada por comas, o "*" para permitir
// cualquiera (comodo en una LAN de confianza, no lo uses de cara a internet).
const allowedHostsEnv = (process.env.VITE_ALLOWED_HOSTS ?? '').trim()
const allowedHosts =
  allowedHostsEnv === '*'
    ? true
    : allowedHostsEnv
        .split(',')
        .map((host) => host.trim())
        .filter(Boolean)

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts,
    // El codigo llega por bind mount desde el host; en algunos entornos
    // (Docker Desktop / WSL) inotify no propaga y hace falta polling.
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
    proxy: {
      '/api': {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
        // Anade X-Forwarded-For para que el rate limiting del login vea la IP
        // del cliente y no la del contenedor del frontend.
        xfwd: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
