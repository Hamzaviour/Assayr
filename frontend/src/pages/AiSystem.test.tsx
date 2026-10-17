import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const SYSTEM = {
  id: "s1", code: "AIS-001", name: "Invoice classifier", purpose: "Invented purpose", owner: null, source: "in_house",
  provider: null, model_type: "classification", lifecycle: "deployed", risk_level: 4, risk_label: "High",
  uses_personal_data: false, pii_categories: [], asset_ids: [], human_oversight: null, status: "active",
  assessment_status: null, created_at: "2026-10-17T08:00:00Z", can_edit: true,
}
const EMPTY = {
  intended_use: null, affected: null, individual_impacts: null, societal_impacts: null, fairness: null,
  transparency: null, oversight: null, safety: null, data_quality: null, conclusion: null,
}

test("starts an assessment, records an impact and raises it to the risk register", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  let assessment: Record<string, unknown> | null = null
  const impact = { id: "i1", area: "fairness", description: "Bias against an invented group", likelihood: 4, impact: 4,
    score: 16, level: 4, mitigation: null, owner: null, risk_id: null as string | null, risk_code: null as string | null }
  const base = () => ({ id: "a1", status: "draft", approved_by: null, approved_at: null, review_due: null, can_edit: true,
    missing: ["affected individuals and groups"], impacts: [] as unknown[], ...EMPTY })
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "ai:manage"] }),
    "GET /ai/systems/s1": () => json(200, SYSTEM),
    "GET /ai/systems/s1/assessment": () => (assessment ? json(200, assessment) : json(404, { detail: "No assessment" })),
    "PUT /ai/systems/s1/assessment": (_url, init) => {
      assessment = { ...base(), ...(assessment ?? {}), ...JSON.parse(String(init.body)) }
      return json(200, assessment)
    },
    "POST /ai/systems/s1/assessment/submit": () => json(409, { detail: "Fill in: affected individuals and groups." }),
    "POST /ai/systems/s1/assessment/impacts": () => {
      assessment = { ...assessment!, impacts: [impact] }
      return json(201, impact)
    },
    "POST /ai/systems/s1/assessment/impacts/i1/raise": () => {
      const raised = { ...impact, risk_id: "r1", risk_code: "RSK-007" }
      assessment = { ...assessment!, impacts: [raised] }
      return json(200, raised)
    },
  })
  renderApp("/ai/s1")
  expect(await screen.findByRole("heading", { name: "Invoice classifier" })).toBeInTheDocument()
  expect(await screen.findByText("No impact assessment yet.")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Start assessment" }))
  expect(await screen.findByLabelText("Intended use and foreseeable misuse")).toBeInTheDocument()
  expect(screen.getByLabelText("Conclusion")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Submit for review" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Fill in: affected individuals and groups.")
  await userEvent.selectOptions(screen.getByLabelText("Area"), "fairness")
  await userEvent.type(screen.getByLabelText("Description"), "Bias against an invented group")
  await userEvent.selectOptions(screen.getByLabelText("Likelihood"), "4")
  await userEvent.selectOptions(screen.getByLabelText("Impact"), "4")
  await userEvent.click(screen.getByRole("button", { name: "Add impact" }))
  expect(await screen.findByText("16")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Raise to risk register" }))
  expect(await screen.findByRole("link", { name: "RSK-007" })).toHaveAttribute("href", "/risks/RSK-007")
})
