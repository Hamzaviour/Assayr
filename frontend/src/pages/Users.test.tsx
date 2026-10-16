import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ADMIN = { ...ME, permissions: [...ME.permissions, "users:manage"] }
const USERS = [
  { ...ME, id: "u1", email: "sana@acme.com", full_name: "Sana Malik", department: "Security", must_change_password: false },
  { ...ME, id: "u2", email: "omar@acme.com", full_name: "Omar Ali", department: "Finance", must_change_password: true, roles: [{ role: "employee", scope_id: null }] },
]

function setup() {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, ADMIN),
    "GET /users": () => json(200, USERS),
    "POST /users/import": () =>
      json(200, {
        created: [{ email: "nadia@acme.com", full_name: "Nadia Noor", temporary_password: "Abcdefgh23456789" }],
        skipped: [{ line: 3, email: "omar@acme.com", reason: "A user with this email already exists." }],
      }),
  })
}

test("lists people with department, roles and first sign-in state", async () => {
  setup()
  renderApp("/users")
  expect(await screen.findByRole("heading", { name: "Users", level: 1 })).toBeInTheDocument()
  const omar = (await screen.findByText("Omar Ali")).closest("tr")!
  expect(omar).toHaveTextContent("Finance")
  expect(omar).toHaveTextContent("Employee")
  expect(omar).toHaveTextContent("Waiting for first sign-in")
})

test("importing a staff CSV shows each temporary password once", async () => {
  const calls = setup()
  renderApp("/users")
  await userEvent.click(await screen.findByRole("button", { name: "Import CSV" }))
  const panel = screen.getByRole("dialog", { name: "Import staff from CSV" })
  const file = new File(["name,email,department\nNadia Noor,nadia@acme.com,IT\nOmar Ali,omar@acme.com,Finance\n"], "staff.csv", { type: "text/csv" })
  await userEvent.upload(within(panel).getByLabelText("Staff list (.csv)"), file)
  expect(await within(panel).findByText("2 people in this file")).toBeInTheDocument()
  await userEvent.click(within(panel).getByRole("button", { name: "Create accounts" }))
  const created = await within(panel).findByRole("table", { name: "Accounts created" })
  expect(created).toHaveTextContent("nadia@acme.com")
  expect(created).toHaveTextContent("Abcdefgh23456789")
  expect(within(created).getByRole("button", { name: "Copy all" })).toBeInTheDocument()
  expect(within(panel).getByText(/Line 3: omar@acme.com/)).toBeInTheDocument()
  expect(within(panel).getByText(/shown only once/i)).toBeInTheDocument()
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/users/import"))).toBe(true)
})
