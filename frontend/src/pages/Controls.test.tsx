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

test("the unowned filter from the dashboard reaches the API and can be cleared", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () => json(200, { items: [row(1, "A.5.1", "Policies for information security")], next_cursor: null }),
  })
  renderApp("/controls?owner=none")
  await screen.findByText("Policies for information security")
  expect(calls.some((c) => c.url.searchParams.get("owner") === "none")).toBe(true)
  await userEvent.click(screen.getByRole("button", { name: "Show all owners" }))
  await screen.findByText("Policies for information security")
  const lists = calls.filter((c) => c.url.pathname.endsWith("/controls"))
  expect(lists[lists.length - 1].url.searchParams.has("owner")).toBe(false)
})

const nia = (ref: string, domain: string, domainName: string, title: string, extra = {}) => ({
  ref, domain, domain_name: domainName, title, status: "not_started", score: null, applicable: true, mandatory: false,
  mapped: [{ code: "A.6.1", title: "Screening", status: "compliant", coverage: "full" }], ...extra,
})

test("the NIA switch lists NIA controls and filters by domain", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () => json(200, { items: [row(1, "A.5.1", "Policies for information security")], next_cursor: null }),
    "GET /nia/controls": () =>
      json(200, [
        nia("PS 1", "PS", "Personnel Security", "Screening before employment", { mandatory: true }),
        nia("AC 3", "AC", "Access Control", "Access reviews", { mapped: [] }),
      ]),
  })
  const { router } = renderApp("/controls")
  await screen.findByText("Policies for information security")
  await userEvent.click(screen.getByRole("radio", { name: "NIA v2.1" }))
  const link = await screen.findByRole("link", { name: "Screening before employment" })
  expect(link).toHaveAttribute("href", "/nia/PS%201")
  expect(screen.getByText("Access reviews")).toBeInTheDocument()
  expect(screen.getByText("NIA only")).toBeInTheDocument()
  expect(screen.getByText("Mandatory")).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText("Domain"), "AC")
  expect(screen.queryByText("Screening before employment")).not.toBeInTheDocument()
  expect(router.state.location.search).toEqual({ framework: "nia", domain: "AC" })
})
