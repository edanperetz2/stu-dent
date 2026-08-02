import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// jsdom doesn't implement matchMedia; Mantine's color-scheme detection needs it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// jsdom doesn't implement ResizeObserver; Mantine's ScrollArea (used by
// Select and other overlay components) needs it. Floating UI (Mantine's
// popover positioning) also waits on a ResizeObserver callback before it
// flips a freshly-opened dropdown's `display: none` to visible, so the
// callback must actually fire -- a no-op mock leaves opened Select
// dropdowns permanently hidden from accessibility queries in tests.
class ResizeObserverMock {
  callback: ResizeObserverCallback
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }
  observe(target: Element) {
    this.callback([{ target } as ResizeObserverEntry], this)
  }
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock)

// jsdom doesn't implement scrollIntoView; Mantine's Combobox (used by
// Select) calls it when keyboard/pointer selection moves the active option.
window.HTMLElement.prototype.scrollIntoView = vi.fn()

// jsdom doesn't implement the FontFaceSet API (document.fonts is
// `undefined`); Mantine's autosize Textarea calls
// document.fonts.addEventListener('loadingdone', ...) to re-measure once
// web fonts finish loading, which crashes with "Cannot read properties of
// undefined (reading 'addEventListener')" for any test that mounts an
// autosize Textarea outside a closed modal/collapsed panel.
Object.defineProperty(document, 'fonts', {
  writable: true,
  value: {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  },
})
