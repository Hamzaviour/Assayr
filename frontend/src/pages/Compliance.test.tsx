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

function setupImport(response: () => Response, me = ME) {
  return mockApi({
    "GET /auth/me": () => json(200, me),
    "GET /dashboard": () =>
      json(200, { frameworks: [ISO, NIA], evidence: { needs_attention: 0, ok: 0, total: 0 }, risks: null, unowned_controls: 0, trend: [] }),
    "POST /frameworks/nia-2.1/import": response,
  })
}

const pdf = () => new File(["%PDF-1.4"], "nia.pdf", { type: "application/pdf" })

test("an ISMS manager imports the official NIA text", async () => {
  const calls = setupImport(() => json(200, { version: "2.1", matched: 188, unmatched: ["AC 1", "AC 2", "AC 3", "AC 4"] }))
  renderApp("/compliance")
  await userEvent.upload(await screen.findByLabelText("Import official text (PDF)"), pdf())
  expect(await screen.findByText("Matched 188 controls · 4 not found")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(post.url.pathname).toBe("/api/v1/frameworks/nia-2.1/import")
  expect(post.init.body).toBeInstanceOf(FormData)
})

test("a wrong version is reported as the server says", async () => {
  setupImport(() => json(422, { detail: "This document shows version 2.0; Assayr expects NIA version 2.1." }))
  renderApp("/compliance")
  await userEvent.upload(await screen.findByLabelText("Import official text (PDF)"), pdf())
  expect(await screen.findByRole("alert")).toHaveTextContent("This document shows version 2.0; Assayr expects NIA version 2.1.")
})

test("people without manager rights see no import", async () => {
  setupImport(() => json(500, {}), { ...ME, permissions: ["controls:read"] })
  renderApp("/compliance")
  await screen.findByText("NIA v2.1")
  expect(screen.queryByLabelText("Import official text (PDF)")).not.toBeInTheDocument()
})


test("framework names open their controls, and PDPPL opens the privacy obligations", async () => {
  const PDPPL = { ...NIA, code: "pdppl-2016", name: "PDPPL", version: "2016", groups: [group("Rights of individuals", 3, 1, 33)] }
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /dashboard": () =>
      json(200, { frameworks: [ISO, NIA, PDPPL], evidence: { needs_attention: 0, ok: 0, total: 0 }, risks: null, unowned_controls: 0, trend: [] }),
  })
  renderApp("/compliance")
  expect(await screen.findByRole("link", { name: /ISO\/IEC 27001/ })).toHaveAttribute("href", "/controls")
  expect(screen.getByRole("link", { name: /NIA v2\.1/ })).toHaveAttribute("href", "/controls?framework=nia")
  expect(screen.getByRole("link", { name: /PDPPL/ })).toHaveAttribute("href", "/privacy?tab=pdppl")
  await userEvent.click(screen.getByRole("button", { name: /Topics/ }))
  expect(screen.getByText("Rights of individuals")).toBeInTheDocument()
})

test("ISO 42001 and SOC 2 cards open their own controls", async () => {
  const AI = { ...ISO, code: "ISO42001:2023", name: "ISO/IEC 42001", version: "2023", groups: [group("AI system life cycle", 9, 2, 30)] }
  const SOC2 = { ...ISO, code: "SOC2:2017", name: "SOC 2", version: "Security", groups: [group("Logical and Physical Access Controls", 8, 1, 10)] }
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /dashboard": () =>
      json(200, { frameworks: [ISO, AI, SOC2], evidence: { needs_attention: 0, ok: 0, total: 0 }, risks: null, unowned_controls: 0, trend: [] }),
  })
  renderApp("/compliance")
  expect(await screen.findByRole("link", { name: /ISO\/IEC 42001/ })).toHaveAttribute("href", "/controls?framework=iso42001")
  expect(screen.getByRole("link", { name: /SOC 2/ })).toHaveAttribute("href", "/controls?framework=soc2")
  const themes = screen.getAllByRole("button", { name: /Themes/ })
  await userEvent.click(themes[1])
  expect(screen.getByRole("link", { name: /AI system life cycle/ })).toHaveAttribute(
    "href",
    "/controls?framework=iso42001&theme=AI+system+life+cycle",
  )
})
