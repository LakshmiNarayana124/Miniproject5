
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    // HTTPS in development: run `npm run dev:https` (see package.json).
    // Vite will self-sign a certificate automatically when https:true is set.
    // For production HTTPS use a reverse proxy (Nginx/Caddy) – see README.
    https: false,   // flip to true or pass --https flag for dev HTTPS

    // Allow access from any device on the local network (phone, tablet, etc.)
    host: true,
    port: 5173,
  },

  preview: {
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
