/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Build provenance: inject the git SHA so the running UI can prove which
// build a participant is seeing (M8-P1-008 forensics).
const buildSha = process.env.EVOSIA_BUILD_SHA || 'unknown'

export default defineConfig({
  plugins: [react()],
  define: {
    __EVOSIA_BUILD_SHA__: JSON.stringify(buildSha),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
