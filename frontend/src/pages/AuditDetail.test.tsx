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
