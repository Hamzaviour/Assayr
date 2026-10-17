import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("each person turns their daily summary email on or off from their name", async () => {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, { ...ME, digest_opt_out: false }),
    "GET /findings": () => json(200, []),
    "PATCH /me/digest": (_u, init) => json(200, { digest_opt_out: JSON.parse(String(init.body)).opt_out }),
  })
  renderApp("/findings")
  await userEvent.click(await screen.findByRole("button", { name: "Sana Malik" }))
  const box = screen.getByRole("checkbox", { name: "Email me a daily summary" })
  expect(box).toBeChecked()
  await userEvent.click(box)
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({ opt_out: true })
  expect(await screen.findByRole("checkbox", { name: "Email me a daily summary" })).not.toBeChecked()
})
