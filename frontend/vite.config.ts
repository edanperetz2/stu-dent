import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Native filesystem events often don't propagate across a Windows-host
    // bind mount into this Linux container, so chokidar's default watcher
    // silently misses file changes -- polling is the standard fix.
    watch: {
      usePolling: true,
      interval: 300,
    },
    // Vite's DNS-rebinding protection rejects any Host header it doesn't
    // recognize by default. This dev server is never what runs in
    // production (a built static bundle is), so allowing the two extra
    // hostnames the E2E suite reaches it through -- the compose network's
    // internal service name, and Docker Desktop's host-gateway alias used
    // from a throwaway test container -- isn't a real security loosening.
    allowedHosts: ['frontend', 'host.docker.internal'],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    // Vitest's default include glob (**/*.{test,spec}.*) also matches the
    // Playwright E2E specs under e2e/ -- those use Playwright's own
    // test()/expect(), not Vitest's, so Vitest must not try to run them.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
