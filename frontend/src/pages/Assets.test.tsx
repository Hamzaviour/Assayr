import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ASSET = {
  id: "a1", code: "AST-001", name: "Core banking database", type: "information",
  owner: { id: "u2", full_name: "Bilal Khan" }, classification: "restricted", confidentiality: 5, integrity: 5,
  availability: 4, criticality: 5, location: "Data centre", description: null, lifecycle: "in_use",
}
const base = {
  "GET /auth/me": () => json(200, ME),
  "GET /assets": () => json(200, [ASSET]),
  "GET /people": () => json(200, [{ id: "u2", full_name: "Bilal Khan", email: "bilal@acme.com", roles: ["control_owner"] }]),
}

test("lists assets with their ratings", async () => {
  mockApi(base)
  renderApp("/assets")
  const row = await screen.findByRole("row", { name: /AST-001/ })
  expect(row).toHaveTextContent("Core banking database")
  expect(row).toHaveTextContent("Restricted")
  expect(row).toHaveTextContent("5 / 5 / 4")
  expect(row).toHaveTextContent("Bilal Khan")
})

test("a manager adds an asset", async () => {
  const calls = mockApi({ ...base, "POST /assets": () => json(201, ASSET) })
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Add asset" }))
  await userEvent.type(screen.getByLabelText("Name"), "File server")
  await userEvent.selectOptions(screen.getByLabelText("Type"), "server")
  await userEvent.selectOptions(screen.getByLabelText("Confidentiality"), "5")
  await userEvent.click(screen.getByRole("button", { name: "Save asset" }))
  await screen.findByRole("button", { name: "Add asset" })
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({
    name: "File server", type: "server", owner_id: null, classification: "internal", confidentiality: 5,
    integrity: 3, availability: 3, location: null, description: null, lifecycle: "in_use",
  })
})

test("an asset is retired from the edit form", async () => {
  const calls = mockApi({ ...base, "PATCH /assets/a1": () => json(200, { ...ASSET, lifecycle: "retired" }) })
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Edit AST-001" }))
  expect(screen.getByLabelText("Name")).toHaveValue("Core banking database")
  await userEvent.selectOptions(screen.getByLabelText("Lifecycle"), "retired")
  await userEvent.click(screen.getByRole("button", { name: "Save asset" }))
  await screen.findByRole("button", { name: "Add asset" })
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toMatchObject({ lifecycle: "retired", owner_id: "u2" })
})
