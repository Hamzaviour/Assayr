import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlDetail } from "../api/types"
import { json, ME, mockApi, renderApp } from "../test/render"

const DETAIL: ControlDetail = {
  id: "c1", scope_id: "s", code: "A.8.13", title: "Information backup", theme: "Technological",
  status: "not_started", implementation_status: "not_started", owner: null, evidence_required: 3,
  description: "Backup copies are maintained and regularly tested.", review_frequency: "Monthly",
  default_owner_role: "IT Manager", implementation_text: null,
  slots: [{ id: "s1", name: "Backup policy", evidence_type: "Policy", required: true, freshness_days: 31, rules: ["V-FMT"] }],
  requirements: [{ ref: "A.8.13", title: "Information backup" }],
}

test("a manager saves the implementation description", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "PATCH /controls/A.8.13": (_url, init) => json(200, { ...DETAIL, ...JSON.parse(String(init.body)) }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByRole("heading", { name: "Information backup" })).toBeInTheDocument()
  expect(screen.getByText("Backup policy")).toBeInTheDocument()
  expect(screen.getByText("Refresh every 31 days")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("How we do it"), "Nightly Veeam jobs.")
  await userEvent.selectOptions(screen.getByLabelText("Implementation status"), "partial")
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Saved")
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({
    implementation_status: "partial",
    implementation_text: "Nightly Veeam jobs.",
  })
  expect(new Headers(patch.init.headers).get("X-CSRF-Token")).toBe("token-xyz")
})

test("people without write access see the description read-only", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: ["controls:read"] }),
    "GET /controls/A.8.13": () => json(200, { ...DETAIL, implementation_text: "Nightly jobs." }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByText("Nightly jobs.")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument()
})

test("an unknown control shows a helpful message", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.9.99": () => json(404, { detail: "Control not found." }),
  })
  renderApp("/controls/A.9.99")
  expect(await screen.findByRole("alert")).toHaveTextContent("Control not found.")
})
