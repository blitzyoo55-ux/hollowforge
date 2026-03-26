import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = dirname(fileURLToPath(import.meta.url))
const workspaceRoot = resolve(rootDir, '../../../../')

function existingDirs(candidates: Array<string | undefined>): string[] {
  const unique = [...new Set(candidates.filter((value): value is string => Boolean(value)))]
  return unique.map((value) => resolve(value)).filter((value) => existsSync(value))
}

const pinokioRootFromEnv = process.env.PINOKIO_ROOT_DIR
const pinokioFsAllowDirs = existingDirs([
  process.env.PINOKIO_OUTPUT_DIR,
  process.env.PINOKIO_PEERS_DIR,
  pinokioRootFromEnv ? resolve(pinokioRootFromEnv, 'drive/drives/peers') : undefined,
  resolve(workspaceRoot, 'pinokio/drive/drives/peers'),
  resolve(homedir(), 'AI_Projects/pinokio/drive/drives/peers'),
  resolve(homedir(), 'AI_projects/pinokio/drive/drives/peers'),
])

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          framework: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          http: ['axios'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
  server: {
    fs: {
      allow: [rootDir, ...pinokioFsAllowDirs],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        timeout: 300_000,
        proxyTimeout: 300_000,
      },
      '/data': {
        target: 'http://localhost:8000',
        timeout: 300_000,
        proxyTimeout: 300_000,
      },
    },
  },
})
