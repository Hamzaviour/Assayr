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

const EMPLOYEE = { ...ME, roles: [{ role: "employee", scope_id: null }], permissions: [] }

test("staff with only the employee role see just My training", async () => {
  mockApi({
    "GET /auth/me": () => json(200, EMPLOYEE),
    "GET /my/assignments": () => json(200, []),
  })
  const { router } = renderApp("/")
  expect(await screen.findByRole("link", { name: "My training" })).toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "Controls" })).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "Home" })).not.toBeInTheDocument()
  await screen.findByRole("heading", { name: "My training", level: 1 })
  expect(router.state.location.pathname).toBe("/my-training")
})

test("managers see My training and Users next to the rest", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "users:manage"] }),
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
  })
  renderApp("/controls")
  expect(await screen.findByRole("link", { name: "My training" })).toHaveAttribute("href", "/my-training")
  expect(screen.getByRole("link", { name: "Users" })).toHaveAttribute("href", "/users")
})
