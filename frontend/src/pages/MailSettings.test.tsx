import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { MailSettings } from "../api/mail"
import { json, ME, mockApi, renderApp } from "../test/render"

const ADMIN = { ...ME, email: "root@acme.com", permissions: [...ME.permissions, "settings:manage", "users:manage"] }
const SAVED: MailSettings = {
  enabled: true, host: "mail.acme.local", port: 587, security: "starttls", username: "assayr@acme.com", password_set: true,
  from_address: "assayr@acme.com", from_name: "Acme GRC", base_url: "https://grc.acme.local", digest_hour: 7,
  key_configured: true, last_run: { day: "2026-10-20", status: "partial", sent: 14, error: "1 failed: dina@acme.com: refused" },
}

function setup(body: MailSettings = SAVED, extra: Record<string, (url: URL, init: RequestInit) => Response> = {}) {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({ "GET /auth/me": () => json(200, ADMIN), "GET /settings/mail": () => json(200, body), ...extra })
  renderApp("/settings/email")
  return calls
}

test("shows the saved settings, keeps the password unless it is changed, and saves", async () => {
  const calls = setup(SAVED, { "PUT /settings/mail": (_u, init) => json(200, { ...SAVED, ...JSON.parse(String(init.body)) }) })
  expect(await screen.findByRole("heading", { name: "Email", level: 1 })).toBeInTheDocument()
  expect(screen.getByLabelText("Mail server")).toHaveValue("mail.acme.local")
  expect(screen.getByText(/A password is saved/)).toBeInTheDocument()
  expect(screen.getByText(/sent to 14 people/)).toBeInTheDocument()
  expect(screen.getByText(/1 failed: dina@acme.com/)).toBeInTheDocument()
  await userEvent.clear(screen.getByLabelText("Port"))
  await userEvent.type(screen.getByLabelText("Port"), "25")
  await userEvent.selectOptions(screen.getByLabelText("Security"), "none")
  await userEvent.click(screen.getByRole("button", { name: "Save" }))
  const put = JSON.parse(String(calls.find((c) => c.method === "PUT")!.init.body))
  expect(put).toMatchObject({ port: 25, security: "none", host: "mail.acme.local", enabled: true })
  expect(put).not.toHaveProperty("password")
  await userEvent.click(screen.getByRole("button", { name: "Change password" }))
  await userEvent.type(screen.getByLabelText("Password"), "Invented-New-1")
  await userEvent.click(screen.getByRole("button", { name: "Save" }))
  expect(JSON.parse(String(calls.filter((c) => c.method === "PUT").at(-1)!.init.body)).password).toBe("Invented-New-1")
})

test("sends a test email and shows the mail server's answer", async () => {
  let ok = true
  setup(SAVED, {
    "POST /settings/mail/test": () => (ok ? json(200, { sent_to: "root@acme.com" }) : json(502, { detail: "The mail server answered 535: bad credentials" })),
  })
  await userEvent.click(await screen.findByRole("button", { name: "Send test email" }))
  expect(await screen.findByText("Test email sent to root@acme.com.")).toBeInTheDocument()
  ok = false
  await userEvent.click(screen.getByRole("button", { name: "Send test email" }))
  expect(await screen.findByText("The mail server answered 535: bad credentials")).toBeInTheDocument()
})

test("warns when the server has no secret key", async () => {
  setup({ ...SAVED, key_configured: false, password_set: false, last_run: null })
  expect(await screen.findByText(/ASSAYR_SECRET_KEY/)).toBeInTheDocument()
})

test("the admin menu links to the email settings", async () => {
  setup()
  expect(await screen.findByRole("link", { name: "Email" })).toHaveAttribute("href", "/settings/email")
})
