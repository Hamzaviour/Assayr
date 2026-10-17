import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { InventoryRow } from "../api/privacy"
import { activity } from "../test/privacy"
import { json, ME, mockApi, renderApp } from "../test/render"

const MANAGER = { ...ME, permissions: [...ME.permissions, "privacy:manage"] }

const ROW: InventoryRow = {
  id: "a1", code: "AST-001", name: "HR system", type: "application", owner: { id: "u1", full_name: "Sana Malik" },
  pii_categories: ["hr", "health"], pii_sensitive: true, pii_volume: "100_1k", criticality: 5, criticality_label: "Very high",
  activities: [{ code: "PA-001", name: "Payroll" }],
}

function setup(me = MANAGER) {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /privacy/summary": () =>
      json(200, { pii_assets: 4, sensitive_assets: 2, activities: 3, active_activities: 2, cross_border: 1, reviews_due: 1 }),
    "GET /privacy/activities": () => json(200, [activity()]),
    "GET /privacy/inventory": () => json(200, [ROW]),
    "POST /privacy/activities": (_u, init) => json(201, activity({ id: "p9", code: "PA-002", ...JSON.parse(String(init.body)) })),
    "GET /privacy/activities/p9": () => json(200, activity({ id: "p9", code: "PA-002", assets: [] })),
    "GET /assets": () => json(200, []),
    "GET /people": () => json(200, []),
  })
}

test("summary strip and processing activities", async () => {
  setup()
  renderApp("/privacy")
  expect(await screen.findByRole("heading", { name: "Data privacy", level: 1 })).toBeInTheDocument()
  const strip = screen.getByRole("list", { name: "Privacy at a glance" })
  await within(strip).findByText("4")
  expect(within(strip).getByText("PII assets").closest("li")).toHaveTextContent("4")
  expect(within(strip).getByText("Cross-border transfers").closest("li")).toHaveTextContent("1")
  const row = (await screen.findByRole("link", { name: "Payroll" })).closest("tr")!
  expect(row).toHaveTextContent("PA-001")
  expect(row).toHaveTextContent("Contract")
  expect(row).toHaveTextContent("Sensitive")
  expect(row).toHaveTextContent("Cross-border")
  expect(row).toHaveTextContent("Review due")
  expect(screen.getByRole("link", { name: /Export Excel/ })).toHaveAttribute("href", "/api/v1/privacy/export.xlsx")
  expect(screen.getByRole("link", { name: "Data privacy" })).toHaveAttribute("aria-current", "page")
})

test("the PII inventory tab lists assets with categories and criticality", async () => {
  setup()
  renderApp("/privacy")
  await userEvent.click(await screen.findByRole("tab", { name: "PII inventory" }))
  const row = (await screen.findByText("HR system")).closest("tr")!
  expect(row).toHaveTextContent("Employee / HR records")
  expect(row).toHaveTextContent("Health")
  expect(row).toHaveTextContent("Very high")
  expect(row).toHaveTextContent("PA-001")
  expect(row).toHaveTextContent("100 – 1,000")
})

test("a new processing activity", async () => {
  const calls = setup()
  const { router } = renderApp("/privacy")
  await userEvent.click(await screen.findByRole("button", { name: "New activity" }))
  const form = screen.getByRole("dialog", { name: "New processing activity" })
  await userEvent.type(within(form).getByLabelText("Name"), "Recruitment")
  await userEvent.selectOptions(within(form).getByLabelText("Lawful basis"), "consent")
  await userEvent.click(within(form).getByRole("button", { name: "Create activity" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toMatchObject({ name: "Recruitment", lawful_basis: "consent", status: "draft" })
  await screen.findByRole("heading", { level: 1, name: /PA-002/ })
  expect(router.state.location.pathname).toBe("/privacy/p9")
})

test("people without privacy rights only read", async () => {
  setup({ ...ME, permissions: ["assets:read"] })
  renderApp("/privacy")
  await screen.findByRole("link", { name: "Payroll" })
  expect(screen.queryByRole("button", { name: "New activity" })).not.toBeInTheDocument()
})
