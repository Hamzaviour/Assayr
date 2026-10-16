import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { audit } from "../test/audits"
import { json, ME, mockApi, renderApp } from "../test/render"

function setup(me = ME) {
  return mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /audits": () => json(200, [audit(), audit({ id: "a2", framework: "iso27001", title: "ISO audit", status: "draft", counts: { total: 0, tested: 0, pass: 0, partial: 0, fail: 0, na: 0 } })]),
    "POST /audits": (_url, init) => json(201, audit({ id: "a9", ...JSON.parse(String(init.body)), status: "draft" })),
    "GET /audits/a9": () => json(200, { ...audit({ id: "a9", status: "draft" }), items: [] }),
    "POST /audits/import": () => json(201, { audit: audit({ id: "a5" }), imported: 258, unknown_refs: ["ZZ 1", "ZZ 2"] }),
  })
}

test("lists audits with framework, status and progress", async () => {
  setup()
  renderApp("/audits")
  expect(await screen.findByRole("heading", { name: "Internal audits", level: 1 })).toBeInTheDocument()
  const row = (await screen.findByRole("link", { name: "NIA internal audit 2026" })).closest("li")!
  expect(row).toHaveTextContent("NIA v2.1")
  expect(row).toHaveTextContent("In progress")
  expect(row).toHaveTextContent("120 of 355 tested")
  expect(within(row).getByRole("img", { name: /110 pass/ })).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "NIA internal audit 2026" })).toHaveAttribute("href", "/audits/a1")
  expect(screen.getByRole("link", { name: "Audits" })).toHaveAttribute("aria-current", "page")
})

test("New audit creates it and opens it", async () => {
  const calls = setup()
  const { router } = renderApp("/audits")
  await userEvent.click(await screen.findByRole("button", { name: "New audit" }))
  const form = screen.getByRole("dialog", { name: "New audit" })
  await userEvent.selectOptions(within(form).getByLabelText("Framework"), "iso27001")
  await userEvent.type(within(form).getByLabelText("Title"), "ISO internal audit Q4")
  await userEvent.click(within(form).getByRole("button", { name: "Create audit" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ framework: "iso27001", title: "ISO internal audit Q4" })
  await screen.findByRole("heading", { level: 1 })
  expect(router.state.location.pathname).toBe("/audits/a9")
})

test("importing a workbook reports what was matched", async () => {
  const calls = setup()
  renderApp("/audits")
  await userEvent.click(await screen.findByRole("button", { name: "Import workbook" }))
  const form = screen.getByRole("dialog", { name: "Import workbook" })
  const file = new File(["xlsx"], "audit.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })
  await userEvent.upload(within(form).getByLabelText("Workbook (.xlsx)"), file)
  expect(await screen.findByText("Imported 258 controls · 2 not found (ZZ 1, ZZ 2)")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST" && c.url.pathname.endsWith("/import"))!
  expect((post.init.body as FormData).get("framework")).toBe("nia-2.1")
})

test("people without audit rights only read", async () => {
  setup({ ...ME, permissions: ["controls:read"] })
  renderApp("/audits")
  await screen.findByRole("link", { name: "NIA internal audit 2026" })
  expect(screen.queryByRole("button", { name: "New audit" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Import workbook" })).not.toBeInTheDocument()
})
