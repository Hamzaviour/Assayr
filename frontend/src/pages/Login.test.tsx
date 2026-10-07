import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("redirects to sign-in and returns to the requested page afterwards", async () => {
  let signedIn = false
  mockApi({
    "GET /auth/me": () => (signedIn ? json(200, ME) : json(401, { detail: "Not signed in." })),
    "POST /auth/login": () => {
      signedIn = true
      return json(200, ME)
    },
  })
  const { router } = renderApp("/styleguide")
  await screen.findByRole("heading", { name: "Sign in to Assayr" })
  expect(router.state.location.search).toEqual({ next: "/styleguide" })
  await userEvent.type(screen.getByLabelText("Email"), "sana@acme.com")
  await userEvent.type(screen.getByLabelText("Password"), "correct-horse-battery")
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }))
  await screen.findByRole("heading", { name: "Styleguide" })
})

test("shows the server's message when sign-in fails", async () => {
  mockApi({
    "GET /auth/me": () => json(401, { detail: "Not signed in." }),
    "POST /auth/login": () =>
      json(401, { detail: "Email or password is incorrect, or the account is temporarily locked." }),
  })
  renderApp("/login")
  await userEvent.type(await screen.findByLabelText("Email"), "sana@acme.com")
  await userEvent.type(screen.getByLabelText("Password"), "wrong-password-here")
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Email or password is incorrect, or the account is temporarily locked.",
  )
})

test("a session that expires mid-use sends the user to sign-in", async () => {
  let signedIn = true
  mockApi({
    "GET /auth/me": () => (signedIn ? json(200, ME) : json(401, { detail: "Your session has expired. Sign in again." })),
  })
  renderApp("/styleguide")
  await screen.findByRole("heading", { name: "Styleguide" })
  signedIn = false
  window.dispatchEvent(new CustomEvent("assayr:unauthorized"))
  await screen.findByRole("heading", { name: "Sign in to Assayr" })
})
