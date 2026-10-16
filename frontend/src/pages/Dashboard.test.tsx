import { screen, within } from "@testing-library/react"
import { METHODOLOGY } from "../test/fixtures"
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
      excluded: 0,
      groups: [],
    },
  ],
  evidence: { needs_attention: 3, ok: 30, total: 33 },
  risks: { open: 4, in_progress: 2, closed: 5, total: 11, by_level: { very_low: 1, low: 2, medium: 5, high: 2, critical: 1 } },
  unowned_controls: 7,
  trend: [
    { date: "2026-10-01", readiness: 40 },
    { date: "2026-10-15", readiness: 52.4 },
  ],
  ...overrides,
})

function setup(body: unknown = dashboard()) {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /dashboard": () => json(200, body),
    "GET /risk-methodology": () => json(200, METHODOLOGY),
  })
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
          excluded: 0,
          groups: [],
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

test("a single day of history explains that the trend builds up", async () => {
  setup(dashboard({ trend: [{ date: "2026-10-16", readiness: 12 }] }))
  expect(await screen.findByText(/Today: 12%/)).toBeInTheDocument()
  expect(screen.getByText(/The trend line appears after the second daily snapshot/)).toBeInTheDocument()
})

test("risk levels follow the methodology, including very low", async () => {
  setup()
  const cell = await screen.findByRole("cell", { name: "Very low" })
  expect(cell.nextSibling).toHaveTextContent("1")
})

test("excluded controls are shown apart from the total", async () => {
  setup(dashboard({ frameworks: [{ ...dashboard().frameworks[0], total: 87, excluded: 6 }] }))
  expect(await screen.findByText(/6 excluded/)).toBeInTheDocument()
})

test("NIA appears under ISO in the compliance section with its name in bold", async () => {
  const nia = { ...dashboard().frameworks[0], code: "nia-2.1", name: "NIA", version: "2.1", total: 355, compliant: 10 }
  setup(dashboard({ frameworks: [dashboard().frameworks[0], nia] }))
  const name = await screen.findByText("NIA v2.1")
  expect(name.tagName).toBe("STRONG")
  const section = name.closest("section")!
  const titles = [...section.querySelectorAll("strong")].map((e) => e.textContent).filter((t) => /ISO|NIA/.test(t ?? ""))
  expect(titles).toEqual(["ISO/IEC 27001", "NIA v2.1"])
  expect(name.closest("article")).toHaveTextContent("10 controls compliant · 355 total")
})
