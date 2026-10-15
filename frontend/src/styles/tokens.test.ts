/// <reference types="node" />
import { readFileSync } from "node:fs"
import { join } from "node:path"

const css = readFileSync(join(__dirname, "tokens.css"), "utf8")

function block(selector: string): string {
  const start = css.indexOf(selector)
  return css.slice(start, css.indexOf("}", start))
}
const value = (scope: string, name: string) => new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`).exec(scope)?.[1]

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a: string, b: string) => {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

test("light theme is maroon on white", () => {
  const light = block(":root {")
  expect(value(light, "primary")?.toUpperCase()).toBe("#8A1538")
  expect(contrast(value(light, "primary")!, value(light, "surface")!)).toBeGreaterThanOrEqual(4.5)
  expect(contrast(value(light, "on-primary")!, value(light, "primary")!)).toBeGreaterThanOrEqual(4.5)
})

test("dark theme maroon stays readable", () => {
  const dark = block(':root[data-theme="dark"]')
  expect(contrast(value(dark, "primary")!, value(dark, "surface")!)).toBeGreaterThanOrEqual(4.5)
  expect(contrast(value(dark, "on-primary")!, value(dark, "primary")!)).toBeGreaterThanOrEqual(4.5)
})

test("chart palette has six colours", () => {
  for (let i = 1; i <= 6; i++) expect(css).toMatch(new RegExp(`--chart-${i}:\\s*#[0-9a-fA-F]{6}`))
})
