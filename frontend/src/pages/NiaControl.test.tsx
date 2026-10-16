import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const DETAIL = {
  ref: "PS 8",
  domain: "PS",
  domain_name: "Personnel Security",
  title: "Return of assets on leaving",
  status: "in_progress",
  score: 40,
  applicable: true,
  mandatory: true,
  mapped: [
    { code: "A.5.11", title: "Return of assets", status: "compliant", coverage: "full" },
    { code: "A.6.5", title: "Responsibilities after termination", status: "not_started", coverage: "partial" },
  ],
  summary: "Our summary of the personnel security domain.",
  text: null as string | null,
  exclusion_reason: null,
  can_edit: true,
}

const DOCS = { policy: [], procedure: [], guideline: [] }

function setup(detail = DETAIL, me = ME) {
  const calls = mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /nia/controls/PS%208": () => json(200, detail),
    "PUT /nia/controls/PS%208/mapping": (_url, init) => {
      const links = JSON.parse(String(init.body)).links as { code: string }[]
      return json(200, { ...detail, mapped: links.map((l) => ({ code: l.code, title: l.code, status: "not_started", coverage: "full" })) })
    },
    "POST /nia/controls/PS%208/applicability": (_url, init) => {
      const body = JSON.parse(String(init.body))
      return json(200, { ...detail, applicable: body.applicable, exclusion_reason: body.reason ?? null })
    },
    "GET /controls/NIA%20PS%208/documents": () => json(404, { detail: "Control not found." }),
    "GET /controls/A.5.11/documents": () => json(200, DOCS),
    "GET /controls/A.6.5/documents": () => json(200, DOCS),
  })
  renderApp("/nia/PS%208")
  return calls
}

test("shows the summary until the official text is imported, and mapped ISO controls with status", async () => {
  setup()
  expect(await screen.findByRole("heading", { name: "Return of assets on leaving", level: 1 })).toBeInTheDocument()
  expect(screen.getByText("Our summary of the personnel security domain.")).toBeInTheDocument()
  expect(screen.getByText(/official text has not been imported/i)).toBeInTheDocument()
  const mapped = screen.getByRole("region", { name: "Mapped ISO controls" })
  expect(within(mapped).getByRole("link", { name: /A\.5\.11/ })).toHaveAttribute("href", "/controls/A.5.11")
  expect(within(mapped).getAllByText("Compliant").length).toBeGreaterThan(0)
})

test("shows the imported text when present", async () => {
  setup({ ...DETAIL, text: "Imported official statement." })
  expect(await screen.findByText("Imported official statement.")).toBeInTheDocument()
  expect(screen.queryByText(/official text has not been imported/i)).not.toBeInTheDocument()
})

test("a manager edits the mapping", async () => {
  const calls = setup()
  const mapped = await screen.findByRole("region", { name: "Mapped ISO controls" })
  await userEvent.click(within(mapped).getByRole("button", { name: "Remove A.6.5" }))
  await userEvent.type(within(mapped).getByLabelText("ISO control"), "a.8.2")
  await userEvent.selectOptions(within(mapped).getByLabelText("Coverage"), "partial")
  await userEvent.click(within(mapped).getByRole("button", { name: "Add" }))
  await userEvent.click(within(mapped).getByRole("button", { name: "Save mapping" }))
  const put = calls.find((c) => c.method === "PUT")!
  expect(JSON.parse(String(put.init.body))).toEqual({
    links: [
      { code: "A.5.11", coverage: "full" },
      { code: "A.8.2", coverage: "partial" },
    ],
  })
})

test("marking a control not applicable needs a reason", async () => {
  const calls = setup()
  const box = await screen.findByRole("checkbox", { name: /applies to us/i })
  await userEvent.click(box)
  const save = screen.getByRole("button", { name: "Save applicability" })
  expect(save).toBeDisabled()
  await userEvent.type(screen.getByLabelText("Why it does not apply"), "No such systems")
  await userEvent.click(save)
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ applicable: false, reason: "No such systems" })
  expect(await screen.findByText(/Not applicable: No such systems/)).toBeInTheDocument()
})

test("people without edit rights see no editors", async () => {
  setup({ ...DETAIL, can_edit: false })
  await screen.findByRole("heading", { name: "Return of assets on leaving", level: 1 })
  expect(screen.queryByRole("button", { name: "Save mapping" })).not.toBeInTheDocument()
  expect(screen.queryByRole("checkbox", { name: /applies to us/i })).not.toBeInTheDocument()
})
