import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const system = (code: string, name: string, lifecycle: string, risk_level: number) => ({
  id: `id-${code}`, code, name, purpose: "Invented purpose", owner: null, source: "in_house", provider: null,
  model_type: "classification", lifecycle, risk_level, risk_label: ["", "Very low", "Low", "Medium", "High", "Very high"][risk_level],
  uses_personal_data: false, pii_categories: [], asset_ids: [], human_oversight: null, status: "active",
  assessment_status: null, created_at: "2026-10-17T08:00:00Z", can_edit: true,
})

test("lists AI systems, filters by lifecycle and registers a new one", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const list = [system("AIS-001", "Invoice classifier", "deployed", 4), system("AIS-002", "Chat helper", "planned", 2)]
  const calls = mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "ai:manage"] }),
    "GET /ai/systems": () => json(200, list),
    "POST /ai/systems": (_url, init) => {
      const created = { ...system("AIS-003", "x", "development", 3), ...JSON.parse(String(init.body)) }
      list.push(created)
      return json(201, created)
    },
  })
  renderApp("/ai")
  expect(await screen.findByRole("link", { name: "Invoice classifier" })).toHaveAttribute("href", "/ai/id-AIS-001")
  expect(screen.getByText("High")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: /Planned: 1/ }))
  expect(screen.queryByText("Invoice classifier")).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: /Planned: 1/ }))
  await userEvent.click(screen.getByRole("button", { name: "Register AI system" }))
  const form = screen.getByRole("form", { name: "Register an AI system" })
  await userEvent.type(within(form).getByLabelText("Name"), "Fraud scorer")
  await userEvent.type(within(form).getByLabelText("Purpose"), "Invented scoring")
  await userEvent.selectOptions(within(form).getByLabelText("Lifecycle"), "development")
  await userEvent.selectOptions(within(form).getByLabelText("Risk level"), "3")
  await userEvent.click(within(form).getByRole("button", { name: "Register" }))
  expect(await screen.findByText("Fraud scorer")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toMatchObject({
    name: "Fraud scorer", purpose: "Invented scoring", lifecycle: "development", risk_level: 3, source: "in_house",
  })
})

test("viewers do not see the register button", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /ai/systems": () => json(200, [{ ...system("AIS-001", "Invoice classifier", "deployed", 4), can_edit: false }]),
  })
  renderApp("/ai")
  await screen.findByText("Invoice classifier")
  expect(screen.queryByRole("button", { name: "Register AI system" })).not.toBeInTheDocument()
})
