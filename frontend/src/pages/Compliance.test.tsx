import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

test("compliance page shows the framework card and a bar per Annex A theme", async () => {
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
          },
        ],
        evidence: { needs_attention: 0, ok: 0, total: 0 },
        risks: null,
        unowned_controls: 0,
        trend: [],
      }),
    "GET /readiness": () =>
      json(200, {
        scope_id: "s",
        readiness: 52,
        status_counts: {},
        by_theme: { Organizational: 60, People: 40, Physical: null, Technological: 55 },
        trend: [],
      }),
  })
  renderApp("/compliance")
  expect(await screen.findByRole("heading", { name: "Compliance", level: 1 })).toBeInTheDocument()
  expect((await screen.findAllByText("ISO/IEC 27001"))[0].tagName).toBe("STRONG")
  expect(await screen.findByRole("progressbar", { name: "Organizational readiness" })).toHaveAttribute("aria-valuenow", "60")
  expect(screen.getByRole("link", { name: /People/ })).toHaveAttribute("href", expect.stringContaining("theme=People"))
  expect(screen.getByRole("link", { name: "Compliance" })).toHaveAttribute("aria-current", "page")
})
