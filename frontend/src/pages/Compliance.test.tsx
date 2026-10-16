import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const group = (name: string, total: number, compliant: number, readiness: number | null) => ({ name, total, compliant, readiness })

const ISO = {
  code: "iso27001",
  name: "ISO/IEC 27001",
  version: "2022",
  total: 93,
  compliant: 40,
  readiness: 52,
  status_counts: { compliant: 40, not_started: 53 },
  excluded: 0,
  groups: [group("Organizational", 37, 20, 60), group("People", 8, 3, 40), group("Physical", 14, 0, null), group("Technological", 34, 17, 55)],
}

const NIA = {
  code: "nia-2.1",
  name: "NIA",
  version: "2.1",
  total: 355,
  compliant: 10,
  readiness: 12,
  status_counts: { compliant: 10, not_started: 345 },
  excluded: 0,
  groups: [{ ...group("Personnel Security", 12, 2, 20), code: "PS" }, { ...group("Access Control", 20, 1, 5), code: "AC" }],
}

function setup() {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /dashboard": () =>
      json(200, { frameworks: [ISO, NIA], evidence: { needs_attention: 0, ok: 0, total: 0 }, risks: null, unowned_controls: 0, trend: [] }),
  })
  renderApp("/compliance")
}

test("one card per framework with the names in bold", async () => {
  setup()
  expect(await screen.findByRole("heading", { name: "Compliance", level: 1 })).toBeInTheDocument()
  expect((await screen.findByText("ISO/IEC 27001")).tagName).toBe("STRONG")
  expect(screen.getByText("NIA v2.1").tagName).toBe("STRONG")
  expect(screen.getByRole("link", { name: "Compliance" })).toHaveAttribute("aria-current", "page")
})

test("ISO themes stay hidden until the Themes button is pressed", async () => {
  setup()
  const themes = await screen.findByRole("button", { name: /Themes/ })
  expect(themes).toHaveAttribute("aria-expanded", "false")
  expect(screen.queryByRole("link", { name: /People/ })).not.toBeInTheDocument()
  await userEvent.click(themes)
  expect(themes).toHaveAttribute("aria-expanded", "true")
  const people = screen.getByRole("link", { name: /People/ })
  expect(people).toHaveAttribute("href", expect.stringContaining("theme=People"))
  expect(people).toHaveTextContent("3 of 8 compliant")
  expect(screen.getByRole("progressbar", { name: "Organizational controls compliant" })).toHaveAttribute("aria-valuenow", "20")
})

test("NIA domains open from the Domains button", async () => {
  setup()
  const domains = await screen.findByRole("button", { name: /Domains/ })
  expect(screen.queryByText("Personnel Security")).not.toBeInTheDocument()
  await userEvent.click(domains)
  expect(domains).toHaveAttribute("aria-expanded", "true")
  expect(screen.getByRole("link", { name: /Personnel Security/ })).toHaveAttribute("href", expect.stringContaining("domain=PS"))
  expect(screen.getByText("2 of 12 compliant")).toBeInTheDocument()
})
