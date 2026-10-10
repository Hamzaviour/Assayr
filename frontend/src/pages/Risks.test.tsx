import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { level, METHODOLOGY, riskRow } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const ROWS = [
  riskRow(),
  riskRow({ id: "r2", code: "R-002", title: "Laptop theft", status: "accepted", inherent: level(4, 3),
    current: level(2, 3), target: level(2, 3) }),
  riskRow({ id: "r3", code: "R-003", title: "New supplier", status: "draft", inherent: null, current: null,
    target: null }),
]

function mockRisks() {
  return mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /risks": () => json(200, ROWS),
    "GET /risk-methodology": () => json(200, METHODOLOGY),
  })
}

test("the table lists risks with their levels", async () => {
  mockRisks()
  renderApp("/risks")
  const row = (await screen.findByRole("link", { name: "Ransomware encrypts file servers" })).closest("tr")!
  expect(row).toHaveTextContent("Critical 20")
  expect(row).toHaveTextContent("High 16")
  expect(row).toHaveTextContent("Medium 8")
  expect(screen.getByRole("link", { name: "New supplier" }).closest("tr")).toHaveTextContent("Draft")
})

test("the heatmap counts risks per cell and lists the risks of a selected cell", async () => {
  mockRisks()
  renderApp("/risks")
  await userEvent.click(await screen.findByRole("button", { name: "Heatmap" }))
  await userEvent.click(screen.getByRole("button", { name: "Likelihood 4, consequence 4: 1 risk" }))
  const selected = screen.getByRole("region", { name: "Selected cell" })
  expect(within(selected).getByRole("link", { name: "Ransomware encrypts file servers" })).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Inherent" }))
  expect(screen.getByRole("button", { name: "Likelihood 4, consequence 5: 1 risk" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Likelihood 4, consequence 3: 1 risk" })).toBeInTheDocument()
})

test("the board groups risks by status", async () => {
  mockRisks()
  renderApp("/risks")
  await userEvent.click(await screen.findByRole("button", { name: "Board" }))
  expect(within(screen.getByRole("region", { name: "Accepted" })).getByText("Laptop theft")).toBeInTheDocument()
  expect(within(screen.getByRole("region", { name: "Draft" })).getByText("New supplier")).toBeInTheDocument()
})
