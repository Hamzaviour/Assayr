import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("signing out ends the session and shows the sign-in page", async () => {
  let signedIn = true
  const calls = mockApi({
    "GET /auth/me": () => (signedIn ? json(200, ME) : json(401, { detail: "Not signed in." })),
    "GET /readiness": () => json(200, { scope_id: "s", readiness: null, status_counts: {}, by_theme: {}, trend: [] }),
    "POST /auth/logout": () => {
      signedIn = false
      return json(204, null)
    },
  })
  renderApp("/")
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }))
  await screen.findByRole("heading", { name: "Sign in to Assayr" })
  expect(calls.some((c) => c.method === "POST" && c.url.pathname === "/api/v1/auth/logout")).toBe(true)
})

test("navigation marks the current page and lists upcoming modules as unavailable", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
  })
  renderApp("/controls")
  expect(await screen.findByRole("link", { name: "Controls" })).toHaveAttribute("aria-current", "page")
  expect(screen.getByRole("link", { name: "Audits" })).toHaveAttribute("href", "/audits")
  expect(screen.getByRole("link", { name: "Policies" })).toHaveAttribute("href", "/policies")
  expect(screen.getByRole("link", { name: "Policies" })).toHaveAttribute("href", "/policies")
})
