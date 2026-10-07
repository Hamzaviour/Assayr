import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

// jsdom does not implement scrolling; the router restores scroll position on navigation.
window.scrollTo = () => {}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.cookie = "assayr_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/"
  delete document.documentElement.dataset.theme
})
