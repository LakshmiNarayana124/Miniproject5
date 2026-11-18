
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// HTTPS certificate configuration
const CERT_DIR = path.resolve(__dirname, '..', 'certs')

const certFile = path.join(CERT_DIR, 'intelliwatch-wifi.crt')
const keyFile = path.join(CERT_DIR, 'intelliwatch-wifi.key')

const hasCerts =
  fs.existsSync(certFile) &&
  fs.existsSync(keyFile)

const httpsOptions = hasCerts
  ? {
      cert: fs.readFileSync(certFile),
      key: fs.readFileSync(keyFile),
    }
  : false

export default defineConfig({
  plugins: [react()],

  // Development server
  server: {
    https: httpsOptions,
    host: true,
    port: 5173,
    strictPort: true,
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
})
