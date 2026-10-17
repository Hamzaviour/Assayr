import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { AuditDetail, AuditItem } from "../api/audits"
import { audit } from "../test/audits"
import { json, ME, mockApi, renderApp } from "../test/render"

const row = (id: string, ref: string, domain: string, extra: Partial<AuditItem> = {}): AuditItem => ({
  id, ref, sort_order: 1, domain, sub_domain: domain, assessment_area: null, test_type: null, requirement: "M",
  result: null, notes: null, ...extra,
})

const ITEMS = [
  row("i1", "SU 5", "System Usage Security", { result: "pass", assessment_area: "Invented area" }),
  row("i2", "SU 7", "System Usage Security"),
  row("i3", "PS 1", "Personnel Security", { result: "partial" }),
]

const detail = (extra: Partial<AuditDetail> = {}): AuditDetail => ({
  ...audit({ counts: { total: 3, tested: 2, pass: 1, partial: 1, fail: 0, na: 0 } }),
  items: ITEMS,
  ...extra,
})

function setup(body: AuditDetail = detail(), me = ME) {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /audits/a1": () => json(200, body),
    "GET /audits": () => json(200, [body]),
    "POST /audits/a1/items": () => json(200, body),
    "PATCH /audits/a1/items/i2": (_url, init) => json(200, { ...ITEMS[1], ...JSON.parse(String(init.body)) }),
    "PATCH /audits/a1/items/i1": (_url, init) => json(200, { ...ITEMS[0], ...JSON.parse(String(init.body)) }),
    "POST /audits/a1/complete": () => json(200, { ...body, status: "completed" }),
    "POST /audits/a1/reopen": () => json(200, { ...body, status: "in_progress" }),
  })
  renderApp("/audits/a1")
  return calls
}

const bodyOf = (calls: ReturnType<typeof setup>, method: string, path: string) =>
  JSON.parse(String(calls.filter((c) => c.method === method && c.url.pathname.endsWith(path)).at(-1)!.init.body))

test("header shows framework, progress and the Excel export", async () => {
  setup()
  expect(await screen.findByRole("heading", { name: "NIA internal audit 2026", level: 1 })).toBeInTheDocument()
  expect(screen.getByText("2 of 3 tested")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: /Export Excel/ })).toHaveAttribute("href", "/api/v1/audits/a1/export.xlsx")
})

test("adding controls: all, a domain, or references", async () => {
  const calls = setup()
  const add = await screen.findByRole("region", { name: "Add controls" })
  await userEvent.click(within(add).getByRole("button", { name: "Add all controls" }))
  expect(bodyOf(calls, "POST", "/items")).toEqual({ all: true })
  await userEvent.type(within(add).getByLabelText("Domain"), "PS")
  await userEvent.click(within(add).getByRole("button", { name: "Add domain" }))
  expect(bodyOf(calls, "POST", "/items")).toEqual({ domain: "PS" })
  await userEvent.type(within(add).getByLabelText("References"), "SU 5, SU 7")
  await userEvent.click(within(add).getByRole("button", { name: "Add references" }))
  expect(bodyOf(calls, "POST", "/items")).toEqual({ refs: ["SU 5", "SU 7"] })
})

test("controls are grouped by domain and results are recorded inline", async () => {
  const calls = setup()
  const group = (await screen.findByRole("heading", { name: "System Usage Security" })).closest("section")!
  expect(within(group).getByRole("link", { name: "SU 7" })).toHaveAttribute("href", "/nia/SU%207")
  await userEvent.selectOptions(within(group).getByLabelText("Result for SU 7"), "fail")
  expect(bodyOf(calls, "PATCH", "/items/i2")).toEqual({ result: "fail" })
  const area = within(group).getByLabelText("Assessment area for SU 5")
  await userEvent.clear(area)
  await userEvent.type(area, "Invented new area")
  await userEvent.tab()
  expect(bodyOf(calls, "PATCH", "/items/i1")).toEqual({ assessment_area: "Invented new area" })
  expect(screen.getByRole("heading", { name: "Personnel Security" })).toBeInTheDocument()
})

test("the Untested filter hides tested controls", async () => {
  setup()
  await screen.findByRole("link", { name: "SU 5" })
  await userEvent.click(screen.getByRole("button", { name: "Untested" }))
  expect(screen.queryByRole("link", { name: "SU 5" })).not.toBeInTheDocument()
  expect(screen.getByRole("link", { name: "SU 7" })).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Fail & partial" }))
  expect(screen.getByRole("link", { name: "PS 1" })).toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "SU 7" })).not.toBeInTheDocument()
})

test("Complete is blocked while controls are untested and works once all are", async () => {
  setup()
  expect(await screen.findByRole("button", { name: "Complete audit" })).toBeDisabled()
  expect(screen.getByText("1 control still needs a result.")).toBeInTheDocument()
})

test("completing a fully tested audit", async () => {
  const tested = detail({ counts: { total: 1, tested: 1, pass: 1, partial: 0, fail: 0, na: 0 }, items: [ITEMS[0]] })
  const calls = setup(tested)
  await userEvent.click(await screen.findByRole("button", { name: "Complete audit" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/complete"))).toBe(true)
})

test("a completed audit is read-only and a manager can reopen it with a reason", async () => {
  const calls = setup(detail({ status: "completed", can_reopen: true }))
  await screen.findByRole("heading", { name: "NIA internal audit 2026", level: 1 })
  expect(screen.queryByLabelText("Result for SU 7")).not.toBeInTheDocument()
  expect(screen.queryByRole("region", { name: "Add controls" })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Reopen" }))
  const confirm = screen.getByRole("button", { name: "Confirm reopen" })
  expect(confirm).toBeDisabled()
  await userEvent.type(screen.getByLabelText("Why reopen?"), "Missed evidence")
  await userEvent.click(confirm)
  expect(bodyOf(calls, "POST", "/reopen")).toEqual({ reason: "Missed evidence" })
})

test("a failed save is shown on the row", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits/a1": () => json(200, detail()),
    "PATCH /audits/a1/items/i2": () => json(409, { detail: "This audit is completed. Reopen it to make changes." }),
  })
  renderApp("/audits/a1")
  await userEvent.selectOptions(await screen.findByLabelText("Result for SU 7"), "fail")
  expect(await screen.findByText("This audit is completed. Reopen it to make changes.")).not.toHaveClass("sr-only")
})

test("the audit details (period, scope, conclusion) can be edited", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits/a1": () => json(200, detail()),
    "GET /people": () => json(200, [{ id: "u1", full_name: "Ali Auditor", email: "ali@acme.com" }]),
    "PATCH /audits/a1": (_url, init) => json(200, { ...detail(), ...JSON.parse(String(init.body)) }),
  })
  renderApp("/audits/a1")
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }))
  await userEvent.type(screen.getByLabelText("Period start"), "2026-10-01")
  await userEvent.type(screen.getByLabelText("Conclusion"), "Invented conclusion")
  await userEvent.click(screen.getByRole("button", { name: "Save details" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toMatchObject({ period_start: "2026-10-01", conclusion: "Invented conclusion" })
})

const SOC2_ITEMS = [
  row("s1", "CC6.1.1", "Logical and Physical Access Controls", {
    sub_domain: "CC6.1", requirement: null, assessment_area: "Invented procedure", result: "no_exception",
    population: "Invented population", sample_size: 25, samples_tested: 25, exception_note: null,
  }),
  row("s2", "CC6.1.2", "Logical and Physical Access Controls", {
    sub_domain: "CC6.1", requirement: null, population: null, sample_size: null, samples_tested: null, exception_note: null,
  }),
]

const soc2Detail = () =>
  detail({
    framework: "soc2",
    title: "SOC 2 Type 2 2026",
    period_start: "2026-01-01",
    period_end: "2026-06-30",
    counts: { total: 2, tested: 1, pass: 0, partial: 0, fail: 0, na: 0, no_exception: 1, exception: 0, not_tested: 0 },
    items: SOC2_ITEMS,
  })

function setupSoc2(patch: (body: Record<string, unknown>) => Response) {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits/a1": () => json(200, soc2Detail()),
    "PATCH /audits/a1/items/s2": (_url, init) => patch(JSON.parse(String(init.body))),
  })
  renderApp("/audits/a1")
  return calls
}

test("a SOC 2 audit shows the period, sample fields and SOC 2 results", async () => {
  const calls = setupSoc2((body) => json(200, { ...SOC2_ITEMS[1], ...body }))
  const header = (await screen.findByRole("heading", { name: "SOC 2 Type 2 2026", level: 1 })).closest("header")!
  expect(header).toHaveTextContent("SOC 2 · Type 2 audit")
  expect(header).toHaveTextContent(/Observation period/)
  expect(header).toHaveTextContent("1 of 2 tested · 1 no exceptions · 0 exceptions · 0 not tested")
  expect(within(header).getByRole("img", { name: /1 no exceptions, 0 exceptions, 0 not tested, 1 untested/ })).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "CC6.1.2" })).toHaveAttribute("href", "/controls/CC6.1.2")
  expect(screen.queryByLabelText("Test type for CC6.1.2")).not.toBeInTheDocument()
  const result = screen.getByLabelText("Result for CC6.1.2")
  expect(within(result).getAllByRole("option").map((o) => o.textContent)).toEqual(["Not recorded", "No exceptions", "Exception", "Not tested"])
  await userEvent.type(screen.getByLabelText("Population for CC6.1.2"), "Invented joiners list")
  await userEvent.tab()
  expect(bodyOf(calls, "PATCH", "/items/s2")).toEqual({ population: "Invented joiners list" })
  await userEvent.type(screen.getByLabelText("Sample size for CC6.1.2"), "25")
  await userEvent.tab()
  expect(bodyOf(calls, "PATCH", "/items/s2")).toEqual({ sample_size: 25 })
  await userEvent.type(screen.getByLabelText("Samples tested for CC6.1.2"), "20")
  await userEvent.tab()
  expect(bodyOf(calls, "PATCH", "/items/s2")).toEqual({ samples_tested: 20 })
  await userEvent.selectOptions(result, "no_exception")
  expect(bodyOf(calls, "PATCH", "/items/s2")).toEqual({ result: "no_exception" })
})

test("choosing Exception without a note shows the server's message on the row", async () => {
  setupSoc2((body) =>
    body.result === "exception" && !body.exception_note ? json(422, { detail: "Describe the exception." }) : json(200, { ...SOC2_ITEMS[1], ...body }),
  )
  await userEvent.selectOptions(await screen.findByLabelText("Result for CC6.1.2"), "exception")
  expect(await screen.findByText("Describe the exception.")).toBeInTheDocument()
  expect(screen.getByLabelText("Exception note for CC6.1.2")).toBeInTheDocument()
})

test("ISO 42001 audit rows open the AI control", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /audits/a1": () =>
      json(200, detail({ framework: "iso42001", title: "AI audit", items: [row("k1", "A.6.2.4", "AI system life cycle", { requirement: null })] })),
  })
  renderApp("/audits/a1")
  expect(await screen.findByRole("link", { name: "A.6.2.4" })).toHaveAttribute("href", "/controls/AI%20A.6.2.4")
  expect(screen.getByText(/ISO\/IEC 42001 · internal audit/)).toBeInTheDocument()
})
