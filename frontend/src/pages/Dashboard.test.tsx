import { screen, within } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

const dashboard = (overrides = {}) => ({
  frameworks: [
    {
      code: "iso27001",
      name: "ISO/IEC 27001",
      version: "2022",
      total: 93,
      compliant: 40,
      readiness: 52.4,
      status_counts: { compliant: 40, in_review: 12, in_progress: 20, at_risk: 0, non_compliant: 0, not_started: 21 },
    },
  ],
  evidence: { needs_attention: 3, ok: 30, total: 33 },
  risks: { open: 4, in_progress: 2, closed: 5, total: 11, by_level: { low: 3, medium: 5, high: 2, critical: 1 } },
  unowned_controls: 7,
  trend: [
    { date: "2026-10-01", readiness: 40 },
    { date: "2026-10-15", readiness: 52.4 },
  ],
  ...overrides,
})

function setup(body: unknown = dashboard()) {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /dashboard": () => json(200, body) })
  renderApp("/")
}

test("framework row shows the name in bold, controls compliant and partial progress", async () => {
  setup()
  const name = await screen.findByText("ISO/IEC 27001")
  expect(name.tagName).toBe("STRONG")
  const row = name.closest("article")!
  expect(row).toHaveTextContent("40 controls compliant · 93 total")
  expect(row).toHaveTextContent("52%")
  expect(within(row).getByRole("cell", { name: "In review" }).nextSibling).toHaveTextContent("12")
})

test("monitoring cards show evidence, risk buckets and unowned controls", async () => {
  setup()
  const risks = (await screen.findByRole("heading", { name: "Risks" })).closest("section")!
  expect(within(risks).getByRole("cell", { name: "Open" }).nextSibling).toHaveTextContent("4")
  expect(within(risks).getByRole("cell", { name: "In progress" }).nextSibling).toHaveTextContent("2")
  expect(within(risks).getByRole("cell", { name: "Closed" }).nextSibling).toHaveTextContent("5")
  expect(screen.getByRole("heading", { name: "Evidence" }).closest("section")).toHaveTextContent("3")
  const owners = screen.getByRole("heading", { name: "Control owners" }).closest("section")!
  expect(owners).toHaveTextContent("7")
  expect(within(owners).getByRole("link")).toHaveAttribute("href", "/controls?owner=none")
})

test("charts are present with text alternatives", async () => {
  setup()
  expect(await screen.findByRole("img", { name: "Readiness over the last 90 days" })).toBeInTheDocument()
  expect(screen.getByRole("img", { name: "Controls by status" })).toBeInTheDocument()
  expect(screen.getByRole("img", { name: "Risks by level" })).toBeInTheDocument()
})

test("no Annex A theme section any more", async () => {
  setup()
  await screen.findByText("ISO/IEC 27001")
  expect(screen.queryByText(/Readiness by Annex A theme/)).not.toBeInTheDocument()
})

test("a fresh install explains the next step and shows no NaN", async () => {
  setup(
    dashboard({
      frameworks: [
        {
          code: "iso27001",
          name: "ISO/IEC 27001",
          version: "2022",
          total: 93,
          compliant: 0,
          readiness: null,
          status_counts: { not_started: 93 },
        },
      ],
      evidence: { needs_attention: 0, ok: 0, total: 0 },
      risks: { open: 0, in_progress: 0, closed: 0, total: 0, by_level: {} },
      trend: [],
    }),
  )
  expect(await screen.findByText(/Upload the first evidence/)).toBeInTheDocument()
  expect(document.body.innerHTML).not.toMatch(/NaN|Infinity/)
})

test("without risk rights the risk card is hidden", async () => {
  setup(dashboard({ risks: null }))
  await screen.findByText("ISO/IEC 27001")
  expect(screen.queryByRole("heading", { name: "Risks" })).not.toBeInTheDocument()
})
