import { defineConfig, devices } from '@playwright/test'

// E2E_BASE_URL lets this run unmodified in two contexts: plain local dev
// (published port, http://localhost:5173) and inside a throwaway container
// attached to the compose network (the internal hostname, http://frontend:5173)
// -- see dev.sh's test-e2e command and .github/workflows/ci.yml's e2e-tests job.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
