import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../../test/render"

const OBLIGATIONS = [
  {
    ref: "PDPPL-09", topic: "Rights of individuals", title: "Let people access their data", summary: "Invented summary.",
    iso: [{ code: "A.5.34", title: "Privacy and protection of PII", status: "in_progress" }],
    evidence: { result: "missing", reason: "1 request(s) overdue: DSR-001." }, status: "at_risk",
  },
  {
    ref: "PDPPL-26", topic: "Records and accountability", title: "Keep a record of processing", summary: "Invented summary two.",
    iso: [{ code: "A.5.9", title: "Inventory", status: "compliant" }],
    evidence: { result: "met", reason: "2 active processing activities." }, status: "compliant",
  },
]

test("obligations are grouped by topic with evidence and the guidance notice", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /privacy/summary": () => json(200, {}),
    "GET /privacy/activities": () => json(200, []),
    "GET /privacy/pdppl": () =>
      json(200, {
        name: "PDPPL", title: "Qatar Personal Data Privacy Protection Law", notice: "Guidance, not legal advice.",
        topics: ["Rights of individuals", "Records and accountability"], total: 2, compliant: 1, obligations: OBLIGATIONS,
      }),
  })
  renderApp("/privacy?tab=pdppl")
  expect(await screen.findByText("Guidance, not legal advice.")).toBeInTheDocument()
  const rights = screen.getByRole("region", { name: "Rights of individuals" })
  const row = within(rights).getByText("Let people access their data").closest("li")!
  expect(row).toHaveTextContent("Missing")
  expect(row).toHaveTextContent("1 request(s) overdue")
  expect(row).toHaveTextContent("At risk")
  expect(within(screen.getByRole("region", { name: "Records and accountability" })).getByText("Met")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Show only gaps" }))
  expect(screen.queryByText("Keep a record of processing")).not.toBeInTheDocument()
})
