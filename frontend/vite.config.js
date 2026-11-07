
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// HTTPS certificate paths
const CERT_DIR = path.resolve(__dirname, '..', 'certs')
const certFile = path.join(CERT_DIR, 'intelliwatch-lan.crt')
const keyFile = path.join(CERT_DIR, 'intelliwatch-lan.key')

const hasCerts = fs.existsSync(certFile) && fs.existsSync(keyFile)

export default defineConfig({
  plugins: [react()],

  server: {
    https: hasCerts
      ? {
          cert: fs.readFileSync(certFile),
          key: fs.readFileSync(keyFile)
        }
      : false,

    host: true,
    port: 5173,
  },

  preview: {
    https: hasCerts
      ? {
          cert: fs.readFileSync(certFile),
          key: fs.readFileSync(keyFile)
        }
      : false,

    host: true,
    port: 4173,
  },

  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'recharts',
              test: /node_modules[\\/](?:recharts|d3-[^\\/]+|victory-vendor)(?:[\\/]|$)/,
              priority: 20,
              minSize: 0,
              maxSize: 250 * 1024,
            },
            {
              name: 'react-vendor',
              test: /node_modules[\\/](?:react|react-dom|react-router|react-router-dom|scheduler)(?:[\\/]|$)/,
              priority: 15,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              priority: 5,
              minSize: 20 * 1024,
              maxSize: 250 * 1024,
            },
          ],
        },
      },
    },
  },
})
