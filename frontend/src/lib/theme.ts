export type Theme = "light" | "dark"
const KEY = "assayr-theme"

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === "light" || value === "dark" ? value : null
  } catch {
    return null
  }
}

export function effectiveTheme(): Theme {
  const explicit = document.documentElement.dataset.theme
  if (explicit === "light" || explicit === "dark") return explicit
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function initTheme(): void {
  const theme = stored()
  if (theme) document.documentElement.dataset.theme = theme
}

export function toggleTheme(): Theme {
  const next: Theme = effectiveTheme() === "dark" ? "light" : "dark"
  document.documentElement.dataset.theme = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* storage blocked: the choice lasts for this page view only */
  }
  return next
}
