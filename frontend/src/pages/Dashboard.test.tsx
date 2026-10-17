import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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
  return renderApp("/")
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
  expect(screen.getByRole("group", { name: "Controls by status" })).toBeInTheDocument()
  expect(screen.getByRole("group", { name: "Risks by level" })).toBeInTheDocument()
})

test("clicking a chart opens the filtered list", async () => {
  const { router } = setup()
  await userEvent.click(await screen.findByRole("button", { name: "In review: 12. Open these" }))
  expect(router.state.location.pathname).toBe("/controls")
  expect(router.state.location.search).toEqual({ status: "in_review" })
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

test("managers see a training card with completion and overdue", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "training:manage"] }),
    "GET /dashboard": () => json(200, dashboard({ training: { assigned: 40, passed: 30, overdue: 5 } })),
    "GET /risk-methodology": () => json(200, METHODOLOGY),
  })
  renderApp("/")
  const card = (await screen.findByRole("heading", { name: "Training" })).closest("section")!
  expect(card).toHaveTextContent("75%")
  expect(card).toHaveTextContent("5 overdue")
  expect(within(card).getByRole("link", { name: /Open training/ })).toHaveAttribute("href", "/training")
})


test("each monitoring card opens its page", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "training:manage"] }),
    "GET /dashboard": () => json(200, dashboard({ training: { assigned: 4, passed: 2, overdue: 1 } })),
    "GET /risk-methodology": () => json(200, METHODOLOGY),
  })
  renderApp("/")
  const monitoring = (await screen.findByRole("heading", { name: "Monitoring" })).closest("section")!
  expect(within(monitoring).getByRole("link", { name: /^Evidence/ })).toHaveAttribute("href", "/evidence")
  expect(within(monitoring).getByRole("link", { name: /^Risks/ })).toHaveAttribute("href", "/risks")
  expect(within(monitoring).getByRole("link", { name: /^Control owners/ })).toHaveAttribute("href", "/controls?owner=none")
  expect(within(monitoring).getByRole("link", { name: /^Training/ })).toHaveAttribute("href", "/training")
})

test("every framework row links to its own controls", async () => {
  const iso = dashboard().frameworks[0]
  setup(
    dashboard({
      frameworks: [
        { ...iso, code: "ISO27001:2022" },
        { ...iso, code: "nia-2.1", name: "NIA", version: "2.1" },
        { ...iso, code: "ISO42001:2023", name: "ISO/IEC 42001", version: "2023" },
        { ...iso, code: "SOC2:2017", name: "SOC 2", version: "Security" },
        { ...iso, code: "pdppl-2016", name: "PDPPL", version: "2016" },
      ],
    }),
  )
  const section = (await screen.findByRole("heading", { name: "Compliance" })).closest("section")!
  const href = (name: RegExp) => within(section).getByRole("link", { name }).getAttribute("href")
  expect(href(/ISO\/IEC 27001/)).toBe("/controls")
  expect(href(/NIA v2\.1/)).toBe("/controls?framework=nia")
  expect(href(/ISO\/IEC 42001/)).toBe("/controls?framework=iso42001")
  expect(href(/SOC 2/)).toBe("/controls?framework=soc2")
  expect(href(/PDPPL/)).toBe("/privacy?tab=pdppl")
})

test("the findings card shows open findings and links to the overdue ones", async () => {
  setup(dashboard({ findings: { open: 5, overdue: 2, by_grade: { major: 1, minor: 3, observation: 1, ofi: 0 }, by_status: {} } }))
  const card = (await screen.findByRole("heading", { name: "Findings" })).closest("section")!
  expect(card).toHaveTextContent("2")
  expect(card).toHaveTextContent("1 major · 3 minor")
  expect(within(card).getByRole("link", { name: /Findings/ })).toHaveAttribute("href", "/findings?overdue=true")
})
