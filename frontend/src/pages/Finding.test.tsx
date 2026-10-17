import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { FindingDetail } from "../api/findings"
import { action, detail } from "../test/findings"
import { json, ME, mockApi, renderApp } from "../test/render"

const PEOPLE = [
  { id: "u2", full_name: "Omar Owner", email: "omar@acme.com" },
  { id: "u3", full_name: "Dina Doer", email: "dina@acme.com" },
]

function setup(body: FindingDetail = detail(), extra: Record<string, (url: URL, init: RequestInit) => Response> = {}) {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /findings/f1": () => json(200, body),
    "GET /people": () => json(200, PEOPLE),
    ...extra,
  })
  renderApp("/findings/f1")
  return calls
}

const lastBody = (calls: ReturnType<typeof setup>, method: string, path: string) =>
  JSON.parse(String(calls.filter((c) => c.method === method && c.url.pathname.endsWith(path)).at(-1)!.init.body))

test("header shows code, grade, status, owner, due date and the source audit", async () => {
  setup()
  const header = (await screen.findByRole("heading", { name: "A.5.1: Fail", level: 1 })).closest("header")!
  expect(header).toHaveTextContent("F-001")
  expect(header).toHaveTextContent("Major NC")
  expect(header).toHaveTextContent("Action planned")
  expect(within(header).getByRole("link", { name: "ISO internal audit 2026" })).toHaveAttribute("href", "/audits/a1")
  expect(within(header).getByRole("link", { name: "A.5.1" })).toHaveAttribute("href", "/controls/A.5.1")
  expect(screen.getByText("Invented description")).toBeInTheDocument()
})

test("root cause and correction are saved", async () => {
  const calls = setup(detail(), { "PATCH /findings/f1": (_u, init) => json(200, { ...detail(), ...JSON.parse(String(init.body)) }) })
  const box = await screen.findByLabelText("Root cause")
  await userEvent.clear(box)
  await userEvent.type(box, "Invented new cause")
  await userEvent.type(screen.getByLabelText("Correction"), "Invented quick fix")
  await userEvent.click(screen.getByRole("button", { name: "Save root cause and correction" }))
  expect(lastBody(calls, "PATCH", "/findings/f1")).toEqual({ root_cause: "Invented new cause", correction: "Invented quick fix" })
})

test("adding a corrective action", async () => {
  const calls = setup(detail(), { "POST /findings/f1/actions": (_u, init) => json(201, action({ id: "c2", seq: 2, ...JSON.parse(String(init.body)) })) })
  const form = await screen.findByRole("form", { name: "Add a corrective action" })
  await userEvent.type(within(form).getByLabelText("Action"), "Invented second action")
  await userEvent.selectOptions(within(form).getByLabelText("Owner"), "u3")
  await userEvent.type(within(form).getByLabelText("Due date"), "2026-11-15")
  await userEvent.click(within(form).getByRole("button", { name: "Add action" }))
  expect(lastBody(calls, "POST", "/actions")).toEqual({ description: "Invented second action", owner_id: "u3", due_date: "2026-11-15" })
})

test("an action owner marks their action done with a note, and the server's message is shown", async () => {
  const calls = setup(detail(), {
    "PATCH /findings/f1/actions/c1": (_u, init) => {
      const body = JSON.parse(String(init.body))
      return body.done_note ? json(200, action({ status: "done", done_note: body.done_note })) : json(422, { detail: "Add a note or a file showing what was done." })
    },
  })
  const item = (await screen.findByText("Invented corrective action")).closest("li")!
  await userEvent.click(within(item).getByRole("button", { name: "Mark done" }))
  expect(await within(item).findByText("Add a note or a file showing what was done.")).toBeInTheDocument()
  await userEvent.type(within(item).getByLabelText("What was done"), "Invented proof")
  await userEvent.click(within(item).getByRole("button", { name: "Mark done" }))
  expect(lastBody(calls, "PATCH", "/actions/c1")).toEqual({ status: "done", done_note: "Invented proof" })
})

test("files are uploaded to an action and listed", async () => {
  const withFile = detail({ actions: [action({ files: [{ id: "x1", filename: "proof.pdf", size: 2048, uploaded_by: { id: "u3", full_name: "Dina Doer" }, uploaded_at: "2026-10-18T10:00:00Z" }] })] })
  const calls = setup(withFile, { "POST /findings/f1/actions/c1/files": () => json(201, withFile.actions[0]) })
  expect(await screen.findByRole("link", { name: /proof\.pdf/ })).toHaveAttribute("href", "/api/v1/findings/f1/actions/c1/files/x1")
  const file = new File(["x"], "more.pdf", { type: "application/pdf" })
  await userEvent.upload(screen.getByLabelText("Attach a file to action 1"), file)
  const upload = calls.find((c) => c.method === "POST" && c.url.pathname.endsWith("/files"))!
  expect((upload.init.body as FormData).get("file")).toBeInstanceOf(File)
})

test("a verifier records the verdict", async () => {
  const waiting = detail({ status: "awaiting_verification", can_verify: true, actions: [action({ status: "done", done_note: "Invented", can_complete: false })] })
  const calls = setup(waiting, { "POST /findings/f1/verify": (_u, init) => json(200, { ...waiting, status: "closed", ...JSON.parse(String(init.body)) }) })
  const section = await screen.findByRole("region", { name: "Verification of effectiveness" })
  const effective = within(section).getByRole("button", { name: "Effective: close the finding" })
  expect(effective).toBeDisabled()
  await userEvent.type(within(section).getByLabelText("What you checked"), "Invented sample of ten")
  await userEvent.click(effective)
  expect(lastBody(calls, "POST", "/verify")).toEqual({ effective: true, note: "Invented sample of ten" })
})

test("people who can not verify see who must", async () => {
  setup(detail({ status: "awaiting_verification", can_verify: false }))
  const section = await screen.findByRole("region", { name: "Verification of effectiveness" })
  expect(section).toHaveTextContent(/someone who did not own this finding or its actions/i)
  expect(within(section).queryByRole("button")).not.toBeInTheDocument()
})

test("observations close with a response", async () => {
  const obs = detail({ grade: "observation", status: "open", root_cause: null, actions: [], can_close: true })
  const calls = setup(obs, { "POST /findings/f1/close": () => json(200, { ...obs, status: "closed" }) })
  await screen.findByRole("heading", { name: "A.5.1: Fail", level: 1 })
  expect(screen.queryByLabelText("Root cause")).not.toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Response"), "Invented: accepted as is")
  await userEvent.click(screen.getByRole("button", { name: "Close with this response" }))
  expect(lastBody(calls, "POST", "/close")).toEqual({ response: "Invented: accepted as is" })
})

test("raise as risk, and the risk link afterwards", async () => {
  const calls = setup(detail(), { "POST /findings/f1/raise-risk": () => json(200, detail({ risk: { id: "r9", code: "R-009" }, can_raise_risk: false })) })
  await userEvent.click(await screen.findByRole("button", { name: "Raise as risk" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/raise-risk"))).toBe(true)
})

test("a closed finding is read-only and a manager can reopen it", async () => {
  const closed = detail({ status: "closed", closed_at: "2026-10-20T10:00:00Z", can_edit: false, can_edit_capa: false, can_add_action: false, can_reopen: true,
    actions: [action({ status: "done", done_note: "Invented", can_complete: false, can_edit: false })],
    verifications: [{ verifier: { id: "u1", full_name: "Ali Auditor" }, effective: true, note: "Invented check", verified_at: "2026-10-20T10:00:00Z" }] })
  const calls = setup(closed, { "POST /findings/f1/reopen": () => json(200, detail()) })
  await screen.findByText("Invented check")
  expect(screen.queryByRole("form", { name: "Add a corrective action" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Mark done" })).not.toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Why reopen?"), "Invented recurrence")
  await userEvent.click(screen.getByRole("button", { name: "Reopen finding" }))
  expect(lastBody(calls, "POST", "/reopen")).toEqual({ reason: "Invented recurrence" })
})
