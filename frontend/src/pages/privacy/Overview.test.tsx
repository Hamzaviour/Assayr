import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../../test/render"

const DPO = { ...ME, permissions: [...ME.permissions, "privacy:manage", "privacy:sensitive"] }
const SUMMARY = {
  pii_assets: 4, sensitive_assets: 2, activities: 3, active_activities: 2, cross_border: 1, reviews_due: 1,
  requests_open: 2, requests_overdue: 1, breaches_open: 1, notifications_overdue: 1, dpia_due: 2, processors_without_dpa: 1,
}
const PROCESSOR = {
  id: "v1", name: "PayCo", service: "Payroll", country: "Qatar", data_categories: ["financial"], dpa_signed: false,
  dpa_date: null, dpa_document_id: null, subprocessors: null, security_review_on: null, security_result: "concerns",
  risk_level: 4, risk_level_label: "High", status: "active", activities: [{ id: "p1", code: "PA-001", name: "Payroll" }], can_edit: true,
}

function setup(me = DPO) {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /privacy/summary": () => json(200, SUMMARY),
    "GET /privacy/pdppl": () => json(200, { name: "PDPPL", title: "", notice: "Guidance, not legal advice.", topics: [], total: 30, compliant: 12, obligations: [] }),
    "GET /privacy/activities": () => json(200, []),
    "GET /privacy/processors": () => json(200, [PROCESSOR]),
    "POST /privacy/processors": (_u, init) => json(201, { ...PROCESSOR, id: "v2", ...JSON.parse(String(init.body)) }),
  })
}

test("the overview shows what needs attention and the PDPPL score", async () => {
  setup()
  renderApp("/privacy")
  const attention = await screen.findByRole("list", { name: "Needs attention" })
  expect(await within(attention).findByText(/1 data subject request overdue/)).toBeInTheDocument()
  expect(within(attention).getByText(/1 breach notification overdue/)).toBeInTheDocument()
  expect(within(attention).getByText(/2 DPIAs to approve/)).toBeInTheDocument()
  expect(within(attention).getByText(/1 processor without an agreement/)).toBeInTheDocument()
  expect(screen.getByRole("progressbar", { name: "PDPPL obligations met" })).toHaveAttribute("aria-valuenow", "12")
  await userEvent.click(within(attention).getByRole("button", { name: /processor without an agreement/ }))
  expect(screen.getByRole("tab", { name: "Processors" })).toHaveAttribute("aria-selected", "true")
})

test("requests and breaches tabs need sensitive access", async () => {
  setup({ ...ME, permissions: ["assets:read"] })
  renderApp("/privacy")
  await screen.findByRole("tab", { name: "Overview" })
  expect(screen.queryByRole("tab", { name: "Requests" })).not.toBeInTheDocument()
  expect(screen.queryByRole("tab", { name: "Breaches" })).not.toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "PDPPL" })).toBeInTheDocument()
})

test("the processors tab lists processors and adds one", async () => {
  const calls = setup()
  renderApp("/privacy?tab=processors")
  const row = (await screen.findByText("PayCo")).closest("tr")!
  expect(row).toHaveTextContent("No agreement")
  expect(row).toHaveTextContent("High")
  expect(row).toHaveTextContent("PA-001")
  await userEvent.click(screen.getByRole("button", { name: "Add processor" }))
  const form = screen.getByRole("dialog", { name: "Add processor" })
  await userEvent.type(within(form).getByLabelText("Name"), "MailCo")
  await userEvent.click(within(form).getByRole("checkbox", { name: "Data processing agreement signed" }))
  await userEvent.click(within(form).getByRole("button", { name: "Save processor" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toMatchObject({ name: "MailCo", dpa_signed: true })
})
