import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

const readiness = (value: number | null) => ({
  scope_id: "s",
  readiness: value,
  status_counts: { not_started: 90, in_progress: 2, compliant: 1 },
  by_theme: { Organizational: value === null ? null : 4.1, People: value === null ? null : 0 },
  trend: [],
})

test("shows readiness, status counts and theme readiness", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /readiness": () => json(200, readiness(2.4)) })
  renderApp("/")
  expect(await screen.findByRole("img", { name: "Readiness 2 percent" })).toBeInTheDocument()
  expect(screen.getByText("Organizational").closest("tr")).toHaveTextContent("4%")
  // label span → pill → the status-count group
  expect(screen.getByText("Compliant").parentElement?.parentElement).toHaveTextContent("Compliant 1")
})

test("explains where readiness will appear before any evidence exists", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /readiness": () => json(200, readiness(null)) })
  renderApp("/")
  expect(await screen.findByText(/Readiness appears once the first evidence is verified/)).toBeInTheDocument()
})
