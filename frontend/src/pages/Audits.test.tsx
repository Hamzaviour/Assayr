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
    "POST /audits/import": () => json(201, { audit: audit({ id: "a5" }), imported: 258, unknown_refs: ["ZZ 1", "ZZ 2"], skipped_rows: ["Row 18: no control reference"] }),
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
  expect(screen.getByText(/Row 18: no control reference/)).toBeInTheDocument()
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

test("the framework list has all four frameworks, and SOC 2 asks for the observation period", async () => {
  const calls = setup()
  renderApp("/audits")
  await userEvent.click(await screen.findByRole("button", { name: "New audit" }))
  const form = screen.getByRole("dialog", { name: "New audit" })
  const select = within(form).getByLabelText("Framework")
  expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["NIA v2.1", "ISO/IEC 27001", "ISO/IEC 42001", "SOC 2"])
  expect(within(form).queryByLabelText("Observation period from")).not.toBeInTheDocument()
  await userEvent.selectOptions(select, "soc2")
  const from = within(form).getByLabelText("Observation period from")
  const to = within(form).getByLabelText("Observation period to")
  expect(from).toBeRequired()
  expect(to).toBeRequired()
  await userEvent.type(within(form).getByLabelText("Title"), "SOC 2 Type 2 2026")
  await userEvent.type(from, "2026-01-01")
  await userEvent.type(to, "2026-06-30")
  await userEvent.click(within(form).getByRole("button", { name: "Create audit" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({
    framework: "soc2", title: "SOC 2 Type 2 2026", period_start: "2026-01-01", period_end: "2026-06-30",
  })
})

test("a SOC 2 audit in the list shows its exceptions", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits": () => json(200, [audit({
      framework: "soc2", title: "SOC 2 Type 2 2026", period_start: "2026-01-01", period_end: "2026-06-30",
      counts: { total: 40, tested: 30, pass: 0, partial: 0, fail: 0, na: 0, no_exception: 26, exception: 3, not_tested: 1 },
    })]),
  })
  renderApp("/audits")
  const row = (await screen.findByRole("link", { name: "SOC 2 Type 2 2026" })).closest("li")!
  expect(row).toHaveTextContent("SOC 2")
  expect(row).toHaveTextContent("30 of 40 tested · 26 no exceptions · 3 exceptions · 1 not tested")
  expect(within(row).getByRole("img", { name: /26 no exceptions, 3 exceptions, 1 not tested, 10 untested/ })).toBeInTheDocument()
})

test("importing a SOC 2 tracker sends the framework and lists unknown numbers", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits": () => json(200, []),
    "POST /audits/import": () => json(201, { audit: audit({ id: "a6", framework: "soc2" }), imported: 61, unknown_refs: ["CC10.1.1"], skipped_rows: [] }),
  })
  renderApp("/audits")
  await userEvent.click(await screen.findByRole("button", { name: "Import workbook" }))
  const form = screen.getByRole("dialog", { name: "Import workbook" })
  await userEvent.selectOptions(within(form).getByLabelText("Framework"), "soc2")
  expect(form).toHaveTextContent(/SOC 2 tracker/)
  const file = new File(["xlsx"], "tracker.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })
  await userEvent.upload(within(form).getByLabelText("Workbook (.xlsx)"), file)
  expect(await screen.findByText("Imported 61 controls · 1 not found (CC10.1.1)")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST" && c.url.pathname.endsWith("/import"))!
  expect((post.init.body as FormData).get("framework")).toBe("soc2")
})
