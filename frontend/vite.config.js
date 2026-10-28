import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev: proxy /api to the backend so the frontend calls same-origin.
    proxy: { '/api': 'http://localhost:8000' }
  }
})
