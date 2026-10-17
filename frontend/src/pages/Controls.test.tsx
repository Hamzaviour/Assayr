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
  ref, own_control: null as string | null, domain, domain_name: domainName, title, status: "not_started", score: null, applicable: true, mandatory: false,
  mapped: [{ code: "A.6.1", title: "Screening", status: "compliant", coverage: "full" }], ...extra,
})

test("the NIA switch lists NIA controls and filters by domain", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () => json(200, { items: [row(1, "A.5.1", "Policies for information security")], next_cursor: null }),
    "GET /nia/controls": () =>
      json(200, [
        nia("PS 1", "PS", "Personnel Security", "Screening before employment", { mandatory: true }),
        nia("AC 3", "AC", "Access Control", "Access reviews", {
          own_control: "NIA AC 3",
          mapped: [{ code: "NIA AC 3", title: "AC 3", status: "not_started", coverage: "full" }],
        }),
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


const ctrl = (n: number, code: string, ref: string, title: string, theme: string, framework: ControlSummary["framework"]) => ({
  ...row(n, code, title, theme), ref, framework,
})

test("switches to ISO 42001 and lists AI controls with their own themes", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () =>
      json(200, { items: [ctrl(1, "AI A.6.2.4", "A.6.2.4", "AI system verification and validation", "AI system life cycle", "iso42001")], next_cursor: null }),
    "GET /controls/summary": () =>
      json(200, { scope_id: "s", total: 1, by_status: { not_started: 1 }, by_theme: { "AI system life cycle": 1 } }),
  })
  renderApp("/controls?framework=iso42001")
  expect(await screen.findByText("A.6.2.4")).toBeInTheDocument()
  expect(screen.getByRole("radio", { name: "ISO/IEC 42001" })).toHaveAttribute("aria-checked", "true")
  expect(screen.getByRole("link", { name: "AI system verification and validation" })).toHaveAttribute(
    "href",
    "/controls/AI%20A.6.2.4",
  )
  expect(screen.getByRole("option", { name: "AI system life cycle" })).toBeInTheDocument()
  expect(calls.some((c) => c.url.pathname.endsWith("/controls") && c.url.searchParams.get("framework") === "iso42001")).toBe(true)
})

test("groups SOC 2 activities under their criterion and adds an activity", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const theme = "Logical and physical access controls"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () =>
      json(200, {
        items: [
          ctrl(1, "CC6.1", "CC6.1", "Logical access security", theme, "soc2"),
          ctrl(2, "CC6.1.1", "CC6.1.1", "Invented MFA control", theme, "soc2"),
          ctrl(3, "CC6.2", "CC6.2", "User registration and credentials", theme, "soc2"),
        ],
        next_cursor: null,
      }),
    "GET /controls/summary": () => json(200, { scope_id: "s", total: 3, by_status: { not_started: 3 }, by_theme: { [theme]: 3 } }),
    "POST /soc2/activities": (_url, init) => json(201, { ...ctrl(4, "CC6.1.2", "CC6.1.2", "x", theme, "soc2"), ...JSON.parse(String(init.body)) }),
  })
  renderApp("/controls?framework=soc2")
  expect(await screen.findByText("1 activity")).toBeInTheDocument()
  expect(screen.queryByText("Invented MFA control")).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Show activities for CC6.1" }))
  expect(screen.getByRole("link", { name: "Invented MFA control" })).toHaveAttribute("href", "/controls/CC6.1.1")
  await userEvent.click(screen.getByRole("button", { name: "Add activity" }))
  await userEvent.type(screen.getByLabelText("Control number"), "CC6.1.2")
  await userEvent.type(screen.getByLabelText("Control"), "Invented review")
  await userEvent.type(screen.getByLabelText("Detailed test of controls"), "Inspected invented tickets.")
  await userEvent.click(screen.getByRole("button", { name: "Add" }))
  await screen.findByRole("button", { name: "Add activity" })
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({
    code: "CC6.1.2",
    title: "Invented review",
    test_procedure: "Inspected invented tickets.",
  })
})
