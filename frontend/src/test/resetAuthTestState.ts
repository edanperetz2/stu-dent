import { vi } from 'vitest'

/** Repeated identically in every test file that mocks the auth API and
 * touches localStorage-backed session state -- deduped to one place. */
export function resetAuthTestState() {
  vi.clearAllMocks()
  localStorage.clear()
}
