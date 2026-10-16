import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlDetail } from "../api/types"
import { doc } from "../test/documents"
import { json, ME, mockApi, renderApp } from "../test/render"

const CONTROL: ControlDetail = {
  id: "c1", scope_id: "s", code: "A.5.1", title: "Policies for information security", theme: "Organizational",
  status: "not_started", implementation_status: "not_started", owner: null, evidence_required: 1, score: null, attestation: null,
  description: "Policies are defined and approved.", review_frequency: "Annual", default_owner_role: null, implementation_text: null,
  slots: [], requirements: [],
}
const ISP = doc("d1", "policy", "POL-01", "Information security policy", { status: "approved" })
const AUP = doc("d2", "policy", "POL-02", "Acceptable use policy")

function setup() {
  let linked = [ISP]
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.5.1": () => json(200, CONTROL),
    "GET /controls/A.5.1/documents": () => json(200, { policy: linked, procedure: [], guideline: [] }),
    "GET /documents": () => json(200, [ISP, AUP]),
    "POST /controls/A.5.1/documents/d2": () => {
      linked = [ISP, AUP]
      return json(200, { policy: linked, procedure: [], guideline: [] })
    },
  })
  renderApp("/controls/A.5.1")
  return calls
}

test("the control page shows policies, procedures and guidelines", async () => {
  setup()
  const policies = await screen.findByRole("button", { name: /Policies\s*1/ })
  await userEvent.click(policies)
  const region = screen.getByRole("region", { name: "Policies" })
  expect(within(region).getByRole("link", { name: /Information security policy/ })).toHaveAttribute("href", "/policies/d1")
  await userEvent.click(screen.getByRole("button", { name: /Procedures\s*0/ }))
  expect(screen.getByText("No procedures linked yet")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /Guidelines\s*0/ })).toHaveAttribute("aria-expanded", "false")
})

test("linking a document from the control page", async () => {
  const calls = setup()
  await userEvent.click(await screen.findByRole("button", { name: /Policies\s*1/ }))
  const region = screen.getByRole("region", { name: "Policies" })
  await userEvent.click(within(region).getByRole("button", { name: "Link a document" }))
  await userEvent.type(within(region).getByLabelText("Find a policy"), "accept")
  expect(within(region).queryByRole("option", { name: /Information security policy/ })).not.toBeInTheDocument()
  await userEvent.click(within(region).getByRole("option", { name: /Acceptable use policy/ }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/controls/A.5.1/documents/d2"))).toBe(true)
  expect(await within(region).findByRole("link", { name: /Acceptable use policy/ })).toBeInTheDocument()
})

test("unlinking a document from the control page", async () => {
  let linked = [ISP]
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.5.1": () => json(200, CONTROL),
    "GET /controls/A.5.1/documents": () => json(200, { policy: linked, procedure: [], guideline: [] }),
    "DELETE /controls/A.5.1/documents/d1": () => {
      linked = []
      return json(200, { policy: [], procedure: [], guideline: [] })
    },
  })
  renderApp("/controls/A.5.1")
  await userEvent.click(await screen.findByRole("button", { name: /Policies\s*1/ }))
  await userEvent.click(screen.getByRole("button", { name: "Unlink POL-01" }))
  expect(calls.some((c) => c.method === "DELETE")).toBe(true)
  expect(await screen.findByText("No policies linked yet")).toBeInTheDocument()
})
