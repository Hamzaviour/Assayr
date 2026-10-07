import { effectiveTheme, initTheme, toggleTheme } from "./theme"

test("toggling flips the theme and remembers it", () => {
  expect(effectiveTheme()).toBe("light")
  expect(toggleTheme()).toBe("dark")
  expect(document.documentElement.dataset.theme).toBe("dark")
  delete document.documentElement.dataset.theme
  initTheme()
  expect(document.documentElement.dataset.theme).toBe("dark")
  localStorage.clear()
})

test("blocked storage does not break theming", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked")
  })
  expect(() => toggleTheme()).not.toThrow()
  vi.restoreAllMocks()
})
