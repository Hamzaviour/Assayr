import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { level, riskDetail } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const base = { "GET /auth/me": () => json(200, ME), "GET /people": () => json(200, []) }

test("shows the levels and controls, and the owner accepts the residual risk", async () => {
  const calls = mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail()),
    "POST /risks/R-001/accept": () => json(200, riskDetail({
      status: "accepted", can_accept: false,
      acceptance: { band: "high", score: 16, authority: "isms_manager", statement: "Accepted for now.",
        accepted_by: "Sana Malik", accepted_at: "2026-10-08T09:00:00Z", expires_at: "2027-10-08T09:00:00Z" },
    })),
  })
  renderApp("/risks/R-001")
  expect(await screen.findByRole("heading", { name: "Ransomware encrypts file servers" })).toBeInTheDocument()
  const levels = screen.getByRole("region", { name: "Risk levels" })
  expect(levels).toHaveTextContent("Critical 20")
  expect(levels).toHaveTextContent("High 16")
  expect(levels).toHaveTextContent("Medium 8")
  expect(screen.getByRole("link", { name: "Information backup" })).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Acceptance statement"), "Accepted for now.")
  await userEvent.click(screen.getByRole("button", { name: "Accept residual risk" }))
  expect(await screen.findByText(/Accepted by Sana Malik on 8 Oct 2026, valid until 8 Oct 2027/)).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ statement: "Accepted for now." })
})

test("explains who has to accept when the user can't", async () => {
  mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail({ current: level(5, 5), can_accept: false, required_authority: "executive" })),
  })
  renderApp("/risks/R-001")
  expect(await screen.findByText("Waiting for acceptance by top management.")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Accept residual risk" })).not.toBeInTheDocument()
})

test("chooses a treatment and adds an action", async () => {
  const planned = riskDetail({
    can_accept: false, status: "treatment_planned", treatment_option: "modify",
    treatment: { option: "modify", note: null, budget: "PKR 2m", due: null },
  })
  const calls = mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail({ can_accept: false })),
    "POST /risks/R-001/treatment": () => json(200, planned),
    "POST /risks/R-001/actions": () => json(201, {
      ...planned, progress: { done: 0, total: 1 },
      actions: [{ id: "t1", title: "Enable MFA", assignee: null, due: null, status: "todo", done_at: null }],
    }),
  })
  renderApp("/risks/R-001")
  await userEvent.click(await screen.findByRole("radio", { name: "Modify" }))
  await userEvent.type(screen.getByLabelText("Budget"), "PKR 2m")
  await userEvent.click(screen.getByRole("button", { name: "Save treatment" }))
  await userEvent.type(await screen.findByLabelText("New action"), "Enable MFA")
  await userEvent.click(screen.getByRole("button", { name: "Add action" }))
  expect(await screen.findByText("Enable MFA")).toBeInTheDocument()
  const posts = calls.filter((c) => c.method === "POST").map((c) => JSON.parse(String(c.init.body)))
  expect(posts).toEqual([
    { option: "modify", note: null, budget: "PKR 2m", due: null },
    { title: "Enable MFA", assignee_id: null, due: null },
  ])
})

const PEOPLE = [
  { id: "u1", full_name: "Sana Malik", email: "s@x", roles: [] },
  { id: "u2", full_name: "Bilal Khan", email: "b@x", roles: [] },
]

test("an editor assigns and clears the owner", async () => {
  const calls = mockApi({
    ...base,
    "GET /people": () => json(200, PEOPLE),
    "GET /risks/R-001": () => json(200, riskDetail()),
    "PATCH /risks/R-001": (_url, init) => {
      const body = JSON.parse(String(init.body))
      return json(200, riskDetail({ owner: body.owner_id ? { id: body.owner_id, full_name: "Bilal Khan" } : null }))
    },
  })
  renderApp("/risks/R-001")
  const picker = await screen.findByRole("combobox", { name: "Risk owner" })
  await screen.findByRole("option", { name: "Bilal Khan" })
  await userEvent.selectOptions(picker, "u2")
  await userEvent.selectOptions(picker, "")
  const patches = calls.filter((c) => c.method === "PATCH").map((c) => JSON.parse(String(c.init.body)))
  expect(patches).toEqual([{ owner_id: "u2" }, { owner_id: null }])
})

test("a deactivated owner is still shown", async () => {
  mockApi({
    ...base,
    "GET /people": () => json(200, PEOPLE),
    "GET /risks/R-001": () => json(200, riskDetail({ owner: { id: "gone", full_name: "Old Owner" } })),
  })
  renderApp("/risks/R-001")
  expect(await screen.findByRole("option", { name: "Old Owner (inactive)" })).toBeInTheDocument()
})

test("someone who cannot edit sees the owner as text", async () => {
  mockApi({ ...base, "GET /risks/R-001": () => json(200, riskDetail({ can_edit: false })) })
  renderApp("/risks/R-001")
  expect(await screen.findByText(/Owner: Sana Malik/)).toBeInTheDocument()
  expect(screen.queryByRole("combobox", { name: "Risk owner" })).not.toBeInTheDocument()
})
