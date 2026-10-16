import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Breach, SubjectRequest } from "../../api/privacy2"
import { json, ME, mockApi, renderApp } from "../../test/render"

const DPO = { ...ME, permissions: [...ME.permissions, "privacy:manage", "privacy:sensitive"] }
const SUMMARY = {
  pii_assets: 0, sensitive_assets: 0, activities: 0, active_activities: 0, cross_border: 0, reviews_due: 0,
  requests_open: 1, requests_overdue: 1, breaches_open: 1, notifications_overdue: 0, dpia_due: 0, processors_without_dpa: 0,
}

const request = (extra: Partial<SubjectRequest> = {}): SubjectRequest => ({
  id: "q1", code: "DSR-001", type: "erasure", requester_name: "Invented Person", requester_contact: "p@example.com",
  channel: "email", received_on: "2026-09-01", due_on: "2026-10-01", days_left: -15, overdue: true,
  identity_verified: false, identity_method: null, assignee: null, activities: [], steps: [], response: null,
  status: "open", outcome: null, refusal_reason: null, closed_on: null, ...extra,
})

const breach = (extra: Partial<Breach> = {}): Breach => ({
  id: "b1", code: "PDB-001", title: "Invented misdirected email", discovered_at: "2026-10-16T08:00:00Z", occurred_at: null,
  description: null, data_categories: ["contact"], people_affected: 40, assets: [], activities: [], severity: "high",
  severity_level: 4, containment: null, regulator_notify: "required", regulator_notified_at: null, people_notify: "undecided",
  people_notified_at: null, notify_deadline: "2026-10-19T08:00:00Z", pending_notifications: ["regulator"], hours_left: 30,
  notification_overdue: false, lessons: null, status: "open", risk: null, ...extra,
})

function setup() {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, DPO),
    "GET /privacy/summary": () => json(200, SUMMARY),
    "GET /privacy/activities": () => json(200, []),
    "GET /privacy/requests": () => json(200, [request()]),
    "POST /privacy/requests": (_u, init) => json(201, request({ id: "q2", code: "DSR-002", ...JSON.parse(String(init.body)) })),
    "GET /privacy/requests/q1": () => json(200, request()),
    "PATCH /privacy/requests/q1": (_u, init) => json(200, request({ ...JSON.parse(String(init.body)), status: "in_progress" })),
    "POST /privacy/requests/q1/close": (_u, init) => json(200, request({ ...JSON.parse(String(init.body)), status: "closed", overdue: false, days_left: null })),
    "GET /privacy/breaches": () => json(200, [breach()]),
    "POST /privacy/breaches": (_u, init) => json(201, breach({ id: "b2", code: "PDB-002", ...JSON.parse(String(init.body)) })),
    "GET /privacy/breaches/b1": () => json(200, breach()),
    "PATCH /privacy/breaches/b1": (_u, init) => json(200, breach(JSON.parse(String(init.body)))),
  })
}

test("requests list shows the deadline and a new one can be logged", async () => {
  const calls = setup()
  renderApp("/privacy?tab=requests")
  const row = (await screen.findByRole("link", { name: "DSR-001" })).closest("tr")!
  expect(row).toHaveTextContent("Erasure")
  expect(row).toHaveTextContent("15 days overdue")
  await userEvent.click(screen.getByRole("button", { name: "Log request" }))
  const form = screen.getByRole("dialog", { name: "Log a data subject request" })
  await userEvent.selectOptions(within(form).getByLabelText("Type"), "access")
  await userEvent.type(within(form).getByLabelText("Requester"), "Another Invented")
  await userEvent.clear(within(form).getByLabelText("Received on"))
  await userEvent.type(within(form).getByLabelText("Received on"), "2026-10-15")
  await userEvent.click(within(form).getByRole("button", { name: "Log request" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toMatchObject({ type: "access", requester_name: "Another Invented", received_on: "2026-10-15" })
})

test("working and closing a request", async () => {
  const calls = setup()
  renderApp("/privacy/requests/q1")
  expect(await screen.findByRole("heading", { level: 1, name: /DSR-001/ })).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("New step"), "Find all records")
  await userEvent.click(screen.getByRole("button", { name: "Add step" }))
  expect(JSON.parse(String(calls.find((c) => c.method === "PATCH")!.init.body))).toEqual({ steps: [{ text: "Find all records", done: false }] })
  await userEvent.selectOptions(screen.getByLabelText("Outcome"), "refused")
  expect(screen.getByRole("button", { name: "Close request" })).toBeDisabled()
  await userEvent.type(screen.getByLabelText("Reason for refusal"), "Manifestly unfounded")
  await userEvent.click(screen.getByRole("button", { name: "Close request" }))
  expect(JSON.parse(String(calls.find((c) => c.url.pathname.endsWith("/close"))!.init.body))).toMatchObject({ outcome: "refused", refusal_reason: "Manifestly unfounded" })
})

test("breaches list shows the notification countdown and severity", async () => {
  setup()
  renderApp("/privacy?tab=breaches")
  const row = (await screen.findByRole("link", { name: "PDB-001" })).closest("tr")!
  expect(row).toHaveTextContent("30 h left to notify")
  expect(row).toHaveTextContent("High")
})

test("recording a breach and its notifications", async () => {
  const calls = setup()
  renderApp("/privacy?tab=breaches")
  await userEvent.click(await screen.findByRole("button", { name: "Record breach" }))
  const form = screen.getByRole("dialog", { name: "Record a personal data breach" })
  await userEvent.type(within(form).getByLabelText("What happened"), "Invented lost laptop")
  await userEvent.selectOptions(within(form).getByLabelText("Severity"), "critical")
  await userEvent.selectOptions(within(form).getByLabelText("Notify the authority"), "required")
  await userEvent.click(within(form).getByRole("button", { name: "Record breach" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toMatchObject({ title: "Invented lost laptop", severity: "critical", regulator_notify: "required" })
})

test("the breach page records that the authority was told", async () => {
  const calls = setup()
  renderApp("/privacy/breaches/b1")
  expect(await screen.findByRole("heading", { level: 1, name: /PDB-001/ })).toBeInTheDocument()
  expect(screen.getByText(/30 hours left/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Mark the authority as notified now" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(Object.keys(JSON.parse(String(patch.init.body)))).toEqual(["regulator_notified_at"])
})
