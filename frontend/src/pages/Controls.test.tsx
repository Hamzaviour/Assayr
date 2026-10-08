import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlSummary } from "../api/types"
import { json, ME, mockApi, renderApp } from "../test/render"

const row = (n: number, code: string, title: string, theme = "Organizational"): ControlSummary => ({
  id: `id-${n}`, scope_id: "s", code, title, theme, status: "not_started",
  implementation_status: "not_started", owner: null, evidence_required: 2, score: null,
})

test("lists controls, loads more and filters by theme through the URL", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": (url) => {
      if (url.searchParams.get("theme") === "People") {
        return json(200, { items: [row(9, "A.6.1", "Screening", "People")], next_cursor: null })
      }
      return url.searchParams.get("cursor") === "2"
        ? json(200, { items: [row(3, "A.5.3", "Segregation of duties")], next_cursor: null })
        : json(200, {
            items: [
              row(1, "A.5.1", "Policies for information security"),
              row(2, "A.5.2", "Information security roles and responsibilities"),
            ],
            next_cursor: 2,
          })
    },
  })
  const { router } = renderApp("/controls")
  expect(await screen.findByRole("link", { name: "Policies for information security" })).toHaveAttribute(
    "href",
    "/controls/A.5.1",
  )
  await userEvent.click(screen.getByRole("button", { name: "Load more" }))
  expect(await screen.findByText("Segregation of duties")).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText("Theme"), "People")
  expect(await screen.findByText("Screening")).toBeInTheDocument()
  expect(router.state.location.search).toEqual({ theme: "People" })
  expect(calls.some((c) => c.url.searchParams.get("theme") === "People")).toBe(true)
})
