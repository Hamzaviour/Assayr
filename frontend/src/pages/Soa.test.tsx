import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const item = (code: string, title: string) => ({
  code, title, theme: "Organizational", applicable: true, sources: [], justification: null, exclusion_reason: null,
  implementation_status: "not_started", status: "not_started", evidence_verified: 0, evidence_required: 2, owner: null,
})
const SOA = {
  items: [
    item("A.5.1", "Policies for information security"),
    item("A.5.2", "Information security roles and responsibilities"),
    item("A.8.30", "Outsourced development"),
  ],
  checks: { orphans: ["A.5.1", "A.5.2", "A.8.30"], excluded_mitigating: [], untreated_risks: ["R-004"], ok: false },
}
const base = {
  "GET /auth/me": () => json(200, ME),
  "GET /soa": () => json(200, SOA),
  "GET /soa/versions": () => json(200, []),
}

test("shows the traceability checks and blocks submission until they pass", async () => {
  mockApi(base)
  renderApp("/soa")
  const checks = await screen.findByRole("region", { name: "Traceability checks" })
  expect(checks).toHaveTextContent("3 applicable controls without a justification")
  expect(checks).toHaveTextContent("1 risk above appetite without a treatment")
  expect(within(checks).getByRole("link", { name: "R-004" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Submit for approval" })).toBeDisabled()
})

test("excluding a control asks for a reason", async () => {
  const calls = mockApi({ ...base, "PATCH /soa/items": () => json(200, SOA) })
  renderApp("/soa")
  await userEvent.click(await screen.findByRole("button", { name: "Exclude A.8.30" }))
  await userEvent.type(screen.getByLabelText("Reason for excluding A.8.30"), "All development is in-house.")
  await userEvent.click(screen.getByRole("button", { name: "Exclude" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({
    codes: ["A.8.30"], applicable: false, exclusion_reason: "All development is in-house.",
  })
})

test("justification sources are set for several controls at once", async () => {
  const calls = mockApi({ ...base, "PATCH /soa/items": () => json(200, SOA) })
  renderApp("/soa")
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select A.5.1" }))
  await userEvent.click(screen.getByRole("checkbox", { name: "Select A.5.2" }))
  const bulk = screen.getByRole("region", { name: "Bulk edit" })
  await userEvent.click(within(bulk).getByRole("checkbox", { name: "Best practice" }))
  await userEvent.click(within(bulk).getByRole("button", { name: "Apply to 2 controls" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({ codes: ["A.5.1", "A.5.2"], sources: ["best_practice"] })
})

test("an executive approves a pending version", async () => {
  const pending = {
    version_no: 1, status: "pending", prepared_by: "Sana Malik", prepared_at: "2026-10-08T09:00:00Z",
    decided_by: null, decided_at: null, decision_note: null, applicable: 93, excluded: 0,
  }
  const calls = mockApi({
    ...base,
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "soa:approve"] }),
    "GET /soa/versions": () => json(200, [pending]),
    "POST /soa/versions/1/approve": () => json(200, { ...pending, status: "approved", decided_by: "Tariq Qureshi" }),
  })
  renderApp("/soa")
  expect(await screen.findByText("v1 is waiting for approval")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Approve v1" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname === "/api/v1/soa/versions/1/approve")).toBe(true)
})
