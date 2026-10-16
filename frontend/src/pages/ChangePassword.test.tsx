import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("a temporary password must be changed before anything else", async () => {
  document.cookie = "assayr_csrf=t; path=/"
  let gated = true
  const calls = mockApi({
    "GET /auth/me": () => json(200, { ...ME, must_change_password: gated }),
    "POST /auth/password": () => {
      gated = false
      return json(204, null)
    },
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
  })
  renderApp("/controls")
  expect(await screen.findByRole("heading", { name: "Choose a new password", level: 1 })).toBeInTheDocument()
  expect(screen.queryByRole("navigation", { name: "Main navigation" })).not.toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Temporary password"), "Temp-Pass-12345")
  await userEvent.type(screen.getByLabelText("New password"), "a-much-better-passphrase")
  await userEvent.type(screen.getByLabelText("Confirm new password"), "a-different-passphrase")
  expect(screen.getByText("The two new passwords don't match.")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Save new password" })).toBeDisabled()
  await userEvent.clear(screen.getByLabelText("Confirm new password"))
  await userEvent.type(screen.getByLabelText("Confirm new password"), "a-much-better-passphrase")
  await userEvent.click(screen.getByRole("button", { name: "Save new password" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ current_password: "Temp-Pass-12345", new_password: "a-much-better-passphrase" })
  expect(await screen.findByRole("link", { name: "Controls" })).toBeInTheDocument()
})

test("a server refusal is shown", async () => {
  document.cookie = "assayr_csrf=t; path=/"
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, must_change_password: true }),
    "POST /auth/password": () => json(422, { detail: "Your current password is not correct." }),
  })
  renderApp("/")
  await userEvent.type(await screen.findByLabelText("Temporary password"), "wrong-password")
  await userEvent.type(screen.getByLabelText("New password"), "a-much-better-passphrase")
  await userEvent.type(screen.getByLabelText("Confirm new password"), "a-much-better-passphrase")
  await userEvent.click(screen.getByRole("button", { name: "Save new password" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Your current password is not correct.")
})
