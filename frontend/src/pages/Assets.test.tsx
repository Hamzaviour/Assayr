import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ASSET = {
  id: "a1", code: "AST-001", name: "Core banking database", type: "information",
  owner: { id: "u2", full_name: "Bilal Khan" }, classification: "restricted", confidentiality: 5, integrity: 5,
  availability: 4, criticality: 5, location: "Data centre", description: null, lifecycle: "in_use",
  confidentiality_label: "Very high", integrity_label: "Very high", availability_label: "High", criticality_label: "Very high",
  holds_pii: true, pii_categories: ["financial", "national_id"], pii_sensitive: false, pii_volume: "gt10k",
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
  expect(row).toHaveTextContent("Very high / Very high / High")
  expect(row).toHaveTextContent("PII")
  const badge = screen.getByTestId("criticality-AST-001")
  expect(badge).toHaveTextContent("Very high")
  expect(badge.getAttribute("style")).toContain("var(--bad)")
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
    holds_pii: false, pii_categories: [], pii_sensitive: false, pii_volume: null,
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


test("C, I and A are chosen in words", async () => {
  mockApi(base)
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Add asset" }))
  const options = [...(screen.getByLabelText("Confidentiality") as HTMLSelectElement).options].map((o) => o.textContent)
  expect(options).toEqual(["Very low", "Low", "Medium", "High", "Very high"])
  await userEvent.selectOptions(screen.getByLabelText("Integrity"), "Very high")
  expect(screen.getByTestId("criticality-preview")).toHaveTextContent("Very high")
})

test("personal data on an asset", async () => {
  const calls = mockApi({ ...base, "POST /assets": () => json(201, ASSET) })
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Add asset" }))
  await userEvent.type(screen.getByLabelText("Name"), "Clinic system")
  expect(screen.queryByRole("checkbox", { name: "Health" })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole("checkbox", { name: "Holds personal data (PII)" }))
  await userEvent.click(screen.getByRole("checkbox", { name: "Health" }))
  await userEvent.click(screen.getByRole("checkbox", { name: "Contact details" }))
  expect(screen.getByRole("checkbox", { name: "Sensitive personal data" })).toBeChecked()
  expect(screen.getByRole("checkbox", { name: "Sensitive personal data" })).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText("Number of people"), "1k_10k")
  await userEvent.click(screen.getByRole("button", { name: "Save asset" }))
  await screen.findByRole("button", { name: "Add asset" })
  const body = JSON.parse(String(calls.find((c) => c.method === "POST")!.init.body))
  expect(body).toMatchObject({ holds_pii: true, pii_categories: ["health", "contact"], pii_sensitive: true, pii_volume: "1k_10k" })
})

test("filters for criticality and personal data reach the API", async () => {
  const calls = mockApi(base)
  renderApp("/assets")
  await screen.findByRole("row", { name: /AST-001/ })
  await userEvent.selectOptions(screen.getByLabelText("Criticality"), "4")
  await userEvent.click(screen.getByRole("checkbox", { name: "Only assets with personal data" }))
  await screen.findByRole("row", { name: /AST-001/ })
  const last = calls.filter((c) => c.url.pathname.endsWith("/assets")).at(-1)!
  expect(last.url.searchParams.get("criticality")).toBe("4")
  expect(last.url.searchParams.get("pii")).toBe("true")
})
