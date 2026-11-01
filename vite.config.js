
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

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
