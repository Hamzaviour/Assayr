import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { doc } from "../test/documents"
import { json, ME, mockApi, renderApp } from "../test/render"

const DOCS = [
  doc("d1", "policy", "POL-01", "Information security policy", { status: "approved", review_due: "2027-10-16" }),
  doc("d2", "policy", "POL-02", "Acceptable use policy", { review_overdue: true, status: "approved", review_due: "2026-01-01" }),
  doc("d3", "procedure", "PRO-01", "Access request procedure"),
]

function setup() {
  return mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /documents": () => json(200, DOCS),
    "POST /documents": (_url, init) => json(201, doc("d9", "guideline", "GUI-01", JSON.parse(String(init.body)).title)),
  })
}

test("three sections with counts that expand to list their documents", async () => {
  setup()
  renderApp("/policies")
  expect(await screen.findByRole("heading", { name: "Policies, procedures and guidelines", level: 1 })).toBeInTheDocument()
  const policies = await screen.findByRole("button", { name: /Policies\s*2/ })
  expect(screen.getByRole("button", { name: /Procedures\s*1/ })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /Guidelines\s*0/ })).toBeInTheDocument()
  expect(policies).toHaveAttribute("aria-expanded", "true")
  const region = screen.getByRole("region", { name: "Policies" })
  expect(within(region).getByRole("link", { name: /Information security policy/ })).toHaveAttribute("href", "/policies/d1")
  expect(within(region).getByText("Review due")).toBeInTheDocument()
  await userEvent.click(policies)
  expect(policies).toHaveAttribute("aria-expanded", "false")
  expect(screen.queryByRole("region", { name: "Policies" })).not.toBeInTheDocument()
  expect(screen.getByRole("link", { name: "Policies" })).toHaveAttribute("aria-current", "page")
})

test("New document creates a draft", async () => {
  const calls = setup()
  renderApp("/policies")
  await userEvent.click(await screen.findByRole("button", { name: "New document" }))
  const dialog = screen.getByRole("dialog", { name: "New document" })
  await userEvent.selectOptions(within(dialog).getByLabelText("Type"), "guideline")
  await userEvent.clear(within(dialog).getByLabelText("Reference"))
  await userEvent.type(within(dialog).getByLabelText("Reference"), "GUI-01")
  await userEvent.type(within(dialog).getByLabelText("Title"), "Password guideline")
  await userEvent.click(within(dialog).getByRole("button", { name: "Create draft" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ doc_type: "guideline", code: "GUI-01", title: "Password guideline" })
})


test("the status bar filters the documents", async () => {
  setup()
  renderApp("/policies")
  await userEvent.click(await screen.findByRole("button", { name: /^Draft: 1/ }))
  expect(screen.getByRole("button", { name: /Policies\s*0/ })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /Procedures\s*1/ })).toBeInTheDocument()
})
