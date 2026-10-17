import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"
import { activity } from "../test/privacy"

const MANAGER = { ...ME, permissions: [...ME.permissions, "privacy:manage"] }
const ASSETS = [
  { id: "a1", code: "AST-001", name: "HR system", criticality: 5, holds_pii: true },
  { id: "a2", code: "AST-002", name: "Mail server", criticality: 3, holds_pii: false },
]

function setup() {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, MANAGER),
    "GET /privacy/activities/p1": () => json(200, activity()),
    "PATCH /privacy/activities/p1": (_u, init) => json(200, activity(JSON.parse(String(init.body)))),
    "PUT /privacy/activities/p1/assets": () => json(200, activity()),
    "GET /assets": () => json(200, ASSETS),
    "GET /people": () => json(200, [{ id: "u1", full_name: "Sana Malik", email: "s@a.com" }]),
  })
}

test("editing an activity", async () => {
  const calls = setup()
  renderApp("/privacy/p1")
  expect(await screen.findByRole("heading", { level: 1, name: /PA-001 · Payroll/ })).toBeInTheDocument()
  expect(screen.getByText("Sensitive")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("checkbox", { name: "Customers" }))
  const retention = screen.getByLabelText("Retention")
  await userEvent.clear(retention)
  await userEvent.type(retention, "10 years")
  await userEvent.click(screen.getByRole("button", { name: "Save activity" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toMatchObject({ data_subjects: ["employees", "customers"], retention: "10 years" })
  expect(await screen.findByText("Saved")).toBeInTheDocument()
})

test("linking the assets where the data is kept", async () => {
  const calls = setup()
  renderApp("/privacy/p1")
  const stored = await screen.findByRole("region", { name: "Where the data is kept" })
  expect(await within(stored).findByRole("checkbox", { name: /HR system/ })).toBeChecked()
  await userEvent.click(within(stored).getByRole("checkbox", { name: /Mail server/ }))
  await userEvent.click(within(stored).getByRole("button", { name: "Save assets" }))
  const put = calls.find((c) => c.method === "PUT")!
  expect(JSON.parse(String(put.init.body))).toEqual({ asset_ids: ["a1", "a2"] })
  expect(within(stored).getByText(/Mail server will be marked as holding personal data/)).toBeInTheDocument()
})
