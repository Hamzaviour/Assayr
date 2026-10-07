import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

test("shows control totals by theme and an explanation where readiness will appear", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/summary": () =>
      json(200, {
        scope_id: "s",
        total: 93,
        by_status: { not_started: 93 },
        by_theme: { Organizational: 37, People: 8, Physical: 14, Technological: 34 },
      }),
  })
  renderApp("/")
  expect((await screen.findByText("Controls in scope")).parentElement).toHaveTextContent("93")
  expect(screen.getByText("Organizational").closest("tr")).toHaveTextContent("37")
  expect(screen.getByText(/Readiness appears once the first evidence is verified/)).toBeInTheDocument()
})
