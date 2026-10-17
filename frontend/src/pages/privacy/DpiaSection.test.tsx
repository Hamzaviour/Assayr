import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Dpia } from "../../api/privacy2"
import { activity } from "../../test/privacy"
import { json, ME, mockApi, renderApp } from "../../test/render"

const DPO = { ...ME, permissions: [...ME.permissions, "privacy:manage", "privacy:sensitive"] }

const dpia = (extra: Partial<Dpia> = {}): Dpia => ({
  id: "d1", status: "draft", screening: { sensitive: true }, recommended: true, description: null, necessity: null,
  consultation: null, conclusion: null, approved_by: null, approved_at: null, review_due: null,
  risks: [
    {
      id: "r1", title: "Unauthorised access", likelihood: 4, impact: 5, score: 20, level: 5, level_label: "Very high",
      measures: "MFA", owner: null, residual_likelihood: 2, residual_impact: 4, residual_score: 8,
      residual_level_label: "Medium", risk: null,
    },
  ],
  can_edit: true,
  ...extra,
})

function setup({ existing = true, basis = "contract" } = {}) {
  document.cookie = "assayr_csrf=t; path=/"
  let current: Dpia | null = existing ? dpia() : null
  return mockApi({
    "GET /auth/me": () => json(200, DPO),
    "GET /privacy/activities/p1": () => json(200, activity({ lawful_basis: basis, processors: [] })),
    "GET /privacy/activities/p1/dpia": () => (current ? json(200, current) : json(404, { detail: "This activity has no DPIA yet." })),
    "PUT /privacy/activities/p1/dpia": (_u, init) => {
      current = { ...(current ?? dpia({ risks: [] })), ...JSON.parse(String(init.body)) }
      return json(200, current)
    },
    "POST /privacy/activities/p1/dpia/risks": () => json(201, dpia().risks[0]),
    "POST /privacy/activities/p1/dpia/risks/r1/raise": () => json(200, { ...dpia().risks[0], risk: { id: "k", code: "R-007" } }),
    "POST /privacy/activities/p1/dpia/submit": () => json(200, dpia({ status: "in_review" })),
    "GET /privacy/processors": () => json(200, [{ id: "v1", name: "PayCo", dpa_signed: false, status: "active" }]),
    "PUT /privacy/activities/p1/processors": () => json(200, activity()),
    "GET /assets": () => json(200, []),
    "GET /people": () => json(200, []),
  })
}

test("screening recommends a DPIA and starts one", async () => {
  const calls = setup({ existing: false })
  renderApp("/privacy/p1")
  const section = await screen.findByRole("region", { name: "Data protection impact assessment" })
  await userEvent.click(await within(section).findByRole("checkbox", { name: "Sensitive personal data" }))
  expect(within(section).getByText("A DPIA is recommended for this activity.")).toBeInTheDocument()
  await userEvent.click(within(section).getByRole("button", { name: "Start DPIA" }))
  const put = calls.find((c) => c.method === "PUT" && c.url.pathname.endsWith("/dpia"))!
  expect(JSON.parse(String(put.init.body))).toEqual({ screening: { sensitive: true } })
})

test("privacy risks are colour-rated and can go to the risk register", async () => {
  const calls = setup()
  renderApp("/privacy/p1")
  const section = await screen.findByRole("region", { name: "Data protection impact assessment" })
  const row = (await within(section).findByText("Unauthorised access")).closest("tr")!
  expect(within(row).getByTestId("score-r1")).toHaveTextContent("20")
  expect(within(row).getByTestId("score-r1").getAttribute("style")).toContain("var(--bad)")
  expect(row).toHaveTextContent("Medium")
  await userEvent.click(within(row).getByRole("button", { name: "Add Unauthorised access to the risk register" }))
  expect(calls.some((c) => c.url.pathname.endsWith("/risks/r1/raise"))).toBe(true)
  await userEvent.type(within(section).getByLabelText("Risk"), "Over-retention")
  await userEvent.selectOptions(within(section).getByLabelText("Likelihood"), "3")
  await userEvent.selectOptions(within(section).getByLabelText("Impact"), "2")
  await userEvent.click(within(section).getByRole("button", { name: "Add risk" }))
  const post = calls.filter((c) => c.method === "POST" && c.url.pathname.endsWith("/dpia/risks")).at(-1)!
  expect(JSON.parse(String(post.init.body))).toMatchObject({ title: "Over-retention", likelihood: 3, impact: 2 })
  await userEvent.click(within(section).getByRole("button", { name: "Submit for review" }))
  expect(calls.some((c) => c.url.pathname.endsWith("/dpia/submit"))).toBe(true)
})

test("consent details show for consent-based processing, and processors can be linked", async () => {
  const calls = setup({ basis: "consent" })
  renderApp("/privacy/p1")
  expect(await screen.findByLabelText("How consent is collected")).toBeInTheDocument()
  expect(screen.getByLabelText("How people withdraw consent")).toBeInTheDocument()
  const processors = screen.getByRole("region", { name: "Processors" })
  await userEvent.click(await within(processors).findByRole("checkbox", { name: /PayCo/ }))
  await userEvent.click(within(processors).getByRole("button", { name: "Save processors" }))
  const put = calls.find((c) => c.method === "PUT" && c.url.pathname.endsWith("/processors"))!
  expect(JSON.parse(String(put.init.body))).toEqual({ processor_ids: ["v1"] })
})
