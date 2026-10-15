import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

const group = (name: string, total: number, compliant: number, readiness: number | null) => ({ name, total, compliant, readiness })

test("compliance page shows the framework card and each Annex A theme with its control counts", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /dashboard": () =>
      json(200, {
        frameworks: [
          {
            code: "iso27001",
            name: "ISO/IEC 27001",
            version: "2022",
            total: 93,
            compliant: 40,
            readiness: 52,
            status_counts: { compliant: 40, not_started: 53 },
            groups: [
              group("Organizational", 37, 20, 60),
              group("People", 8, 3, 40),
              group("Physical", 14, 0, null),
              group("Technological", 34, 17, 55),
            ],
          },
        ],
        evidence: { needs_attention: 0, ok: 0, total: 0 },
        risks: null,
        unowned_controls: 0,
        trend: [],
      }),
  })
  renderApp("/compliance")
  expect(await screen.findByRole("heading", { name: "Compliance", level: 1 })).toBeInTheDocument()
  expect((await screen.findAllByText("ISO/IEC 27001"))[0].tagName).toBe("STRONG")
  expect(screen.getByRole("progressbar", { name: "Organizational controls compliant" })).toHaveAttribute("aria-valuenow", "20")
  const people = screen.getByRole("link", { name: /People/ })
  expect(people).toHaveAttribute("href", expect.stringContaining("theme=People"))
  expect(people).toHaveTextContent("3 of 8 compliant")
  expect(screen.getByRole("link", { name: "Compliance" })).toHaveAttribute("aria-current", "page")
})
