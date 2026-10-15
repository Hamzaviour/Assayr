import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Assessment } from "../api/types"
import { level, METHODOLOGY, riskDetail } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const LIBRARY = {
  threats: [{ code: "T01", name: "Ransomware", category: "Malicious software", description: null, is_custom: false }],
  vulnerabilities: [{ code: "V17", name: "No backups, or backups never tested", category: "Technical", description: null, is_custom: false }],
  templates: [
    { code: "RT01", title: "Ransomware encrypts file servers", scenario: "Ransomware spreads across the network.",
      category: "Cyber attack", threat_codes: ["T01"], vulnerability_codes: ["V17"], control_codes: ["A.8.13"],
      likelihood: 3, consequence: { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 } },
    { code: "RT14", title: "Backups fail when a restore is needed", scenario: "Restores fail.", category: "Availability",
      threat_codes: [], vulnerability_codes: ["V17"], control_codes: ["A.8.13"], likelihood: 3,
      consequence: { financial: 3, operational: 4, legal: 2, reputation: 2, data: 3 } },
  ],
}

function assessment(overrides: Partial<Assessment> = {}): Assessment {
  return {
    id: "a1", likelihood: null, consequence: {}, inherent: null, suggested: null, current: null, current_reason: null,
    target: null, rationale: null, finalized_at: null, assessed_by: "Sana Malik", methodology_version: 1, ...overrides,
  }
}

const DRAFT = riskDetail({
  status: "draft", inherent: null, current: null, target: null, controls: [], draft: assessment(),
  required_authority: null, can_accept: false,
})
const common = {
  "GET /auth/me": () => json(200, ME),
  "GET /risk-library": () => json(200, LIBRARY),
  "GET /risk-methodology": () => json(200, METHODOLOGY),
  "GET /people": () => json(200, []),
}

test("a template starts a new risk and opens the wizard", async () => {
  const calls = mockApi({
    ...common,
    "POST /risks": () => json(201, DRAFT),
    "GET /risks/R-001": () => json(200, DRAFT),
  })
  renderApp("/risks/new")
  await userEvent.click(await screen.findByRole("button", { name: "Use template: Ransomware encrypts file servers" }))
  expect(await screen.findByRole("heading", { name: /Assess R-001/ })).toBeInTheDocument()
  expect(JSON.parse(String(calls.find((c) => c.method === "POST")!.init.body))).toEqual({ template_code: "RT01" })
})

test("rating likelihood and consequence moves the live position", async () => {
  let draft = assessment()
  const calls = mockApi({
    ...common,
    "GET /assets": () => json(200, []),
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
    "GET /risks/R-001": () => json(200, { ...DRAFT, draft }),
    "PATCH /risks/R-001": () => json(200, { ...DRAFT, draft }),
    "PATCH /risks/R-001/assessment": (_url, init) => {
      draft = { ...draft, ...JSON.parse(String(init.body)) }
      return json(200, { ...DRAFT, draft })
    },
  })
  renderApp("/risks/R-001/assess")
  await screen.findByRole("heading", { name: "What could happen?" })
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "Which assets are affected?" })
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "How likely is it to happen?" })
  await userEvent.click(screen.getByRole("radio", { name: "4 · Likely" }))
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "How bad would it be? Rate each area." })
  const choices = [["Financial", 4], ["Operational", 5], ["Legal / regulatory", 3], ["Reputation", 4], ["Data (C/I/A)", 4]] as const
  for (const [area, value] of choices) {
    await userEvent.click(screen.getByRole("radio", { name: `${area} ${value}` }))
  }
  const panel = screen.getByRole("complementary", { name: "Live position" })
  expect(panel).toHaveTextContent("Inherent: L4 × C5 = 20 · Critical")
  expect(panel).toHaveTextContent("Above appetite")
  expect(screen.getByText("Overall consequence = highest = 5 (Severe)")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "Which controls already reduce this risk?" })
  const bodies = calls
    .filter((c) => c.method === "PATCH" && c.url.pathname.endsWith("/assessment"))
    .map((c) => JSON.parse(String(c.init.body)))
  expect(bodies).toEqual([
    { likelihood: 4 },
    { consequence: { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 } },
  ])
})

test("finishing the assessment finalizes it and opens the risk", async () => {
  const ratings = { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 }
  const ready = {
    ...DRAFT,
    draft: assessment({ likelihood: 4, consequence: ratings, inherent: level(4, 5), suggested: level(2, 5) }),
  }
  const assessed = riskDetail({ status: "assessed", draft: null, current: level(2, 5), target: level(2, 5) })
  const calls = mockApi({
    ...common,
    "GET /risks/R-001": () => json(200, ready),
    "PATCH /risks/R-001/assessment": () => json(200, ready),
    "POST /risks/R-001/assessment/finalize": () => json(200, assessed),
  })
  renderApp("/risks/R-001/assess")
  await userEvent.click(await screen.findByRole("button", { name: "6 Result" }))
  expect(screen.getByText("Above appetite. Treat, or accept with the risk owner's justification.")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Finish assessment" }))
  expect(await screen.findByRole("region", { name: "Risk levels" })).toBeInTheDocument()
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({ target_l: null, target_c: null, rationale: null })
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/finalize"))).toBe(true)
})

test("a new risk can be created with an owner", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /people": () => json(200, [{ id: "u2", full_name: "Bilal Khan", email: "b@x", roles: [] }]),
    "GET /risk-library": () => json(200, { threats: [], vulnerabilities: [], templates: [] }),
    "POST /risks": () => json(201, { code: "R-009" }),
    "GET /risks/R-009": () => json(404, { detail: "not needed" }),
  })
  renderApp("/risks/new")
  await screen.findByRole("option", { name: "Bilal Khan" })
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Risk owner" }), "u2")
  await userEvent.type(screen.getByLabelText("Your own scenario"), "Supplier leaks data")
  await userEvent.click(screen.getByRole("button", { name: "Start assessment" }))
  const post = await vi.waitFor(() => {
    const found = calls.find((c) => c.method === "POST")
    if (!found) throw new Error("no POST yet")
    return found
  })
  expect(JSON.parse(String(post.init.body))).toEqual({ title: "Supplier leaks data", owner_id: "u2" })
})
