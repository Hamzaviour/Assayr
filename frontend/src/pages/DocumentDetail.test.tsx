import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { doc } from "../test/documents"
import { json, ME, mockApi, renderApp } from "../test/render"

const DETAIL = {
  ...doc("d1", "policy", "POL-01", "Information security policy", { filename: "isp.pdf", size: 2048 }),
  controls: [{ code: "A.5.1", title: "Policies for information security", status: "in_progress" }],
  history: [{ at: "2026-10-16T09:00:00Z", actor: "sana@acme.com", action: "document.create" }],
}

function setup(detail = DETAIL) {
  return mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /documents/d1": () => json(200, detail),
    "POST /documents/d1/approve": () => json(200, { ...detail, status: "approved" }),
    "POST /documents/d1/file": () => json(200, { ...detail, filename: "new.pdf" }),
  })
}

test("shows details, file download, linked controls and history", async () => {
  setup()
  renderApp("/policies/d1")
  expect(await screen.findByRole("heading", { name: "Information security policy", level: 1 })).toBeInTheDocument()
  expect(screen.getByRole("link", { name: /Download isp\.pdf/ })).toHaveAttribute("href", "/api/v1/documents/d1/file")
  const controls = screen.getByRole("region", { name: "Linked controls" })
  expect(within(controls).getByRole("link", { name: /A\.5\.1/ })).toHaveAttribute("href", "/controls/A.5.1")
  expect(screen.getByText("Created")).toBeInTheDocument()
})

test("a manager approves a draft and uploads a new file", async () => {
  const calls = setup()
  renderApp("/policies/d1")
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/approve"))).toBe(true)
  const file = new File(["%PDF-1.4"], "new.pdf", { type: "application/pdf" })
  await userEvent.upload(screen.getByLabelText("Upload a new file"), file)
  const upload = calls.find((c) => c.method === "POST" && c.url.pathname.endsWith("/file"))!
  expect(upload.init.body).toBeInstanceOf(FormData)
})

test("people who cannot approve see no Approve button", async () => {
  setup({ ...DETAIL, can_approve: false, can_edit: false })
  renderApp("/policies/d1")
  await screen.findByRole("heading", { name: "Information security policy", level: 1 })
  expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument()
  expect(screen.queryByLabelText("Upload a new file")).not.toBeInTheDocument()
})
