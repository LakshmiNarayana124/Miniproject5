/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// HTTPS certificate configuration
const CERT_DIR = path.resolve(__dirname, '..', 'certs')

// Use mkcert-generated cert (trusted by OS) for local HTTPS dev.
// Falls back to plain HTTP if certs are missing.
const certFile = path.join(CERT_DIR, 'intelliwatch-local.crt')
const keyFile  = path.join(CERT_DIR, 'intelliwatch-local.key')

const httpsOptions = fs.existsSync(certFile) && fs.existsSync(keyFile)
  ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }
  : false

export default defineConfig({
  plugins: [react()],

  // Development server
  server: {
    https: httpsOptions,
    host: true,
    port: 5173,
    strictPort: true,
    // Proxy all API/WS routes to the FastAPI backend so VITE_API_URL=/
    // (same-origin) works for both localhost and network access.
    proxy: {
      '/auth':        { target: 'https://localhost:8000', secure: false },
      '/stream':      { target: 'https://localhost:8000', ws: true, secure: false },
      '/control':     { target: 'https://localhost:8000', secure: false },
      '/models':      { target: 'https://localhost:8000', secure: false },
      '/learning':    { target: 'https://localhost:8000', secure: false },
      '/explorer':    { target: 'https://localhost:8000', secure: false },
      '/iot':         { target: 'https://localhost:8000', secure: false },
      '/audit':       { target: 'https://localhost:8000', secure: false },
      '/sensors':     { target: 'https://localhost:8000', secure: false },
      '/chatbot':     { target: 'https://localhost:8000', secure: false },
      '/vision':      { target: 'https://localhost:8000', secure: false },
      '/docs':        { target: 'https://localhost:8000', secure: false },
      '/openapi.json':{ target: 'https://localhost:8000', secure: false },
      '/leaderboard': { target: 'https://localhost:8000', secure: false },
    },
  },

  // Production preview server
  preview: {
    https: httpsOptions,
    host: true,
    port: 4173,
    strictPort: true,
  },

  // Use Vite/Rolldown default dependency splitting.
  // Avoid manually separating Recharts, D3 and React dependencies.
  build: {
    sourcemap: false,
  },

  // Vitest configuration
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [],
  },
})
