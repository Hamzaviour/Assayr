import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlDetail } from "../api/types"
import { json, ME, mockApi, renderApp } from "../test/render"

const DETAIL: ControlDetail = {
  id: "c1", scope_id: "s", code: "A.8.13", title: "Information backup", theme: "Technological",
  status: "not_started", implementation_status: "not_started", owner: null, evidence_required: 3, score: null, attestation: null,
  description: "Backup copies are maintained and regularly tested.", review_frequency: "Monthly",
  default_owner_role: "IT Manager", implementation_text: null,
  slots: [{ id: "s1", name: "Backup policy", evidence_type: "Policy", required: true, freshness_days: 31, rules: ["V-FMT"],
    state: "missing", artefact: null }],
  requirements: [{ ref: "A.8.13", title: "Information backup" }],
}

test("a manager saves the implementation description", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "PATCH /controls/A.8.13": (_url, init) => json(200, { ...DETAIL, ...JSON.parse(String(init.body)) }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByRole("heading", { name: "Information backup" })).toBeInTheDocument()
  expect(screen.getByText("Backup policy")).toBeInTheDocument()
  expect(screen.getByText("Refresh every 31 days")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("How we do it"), "Nightly Veeam jobs.")
  await userEvent.selectOptions(screen.getByLabelText("Implementation status"), "partial")
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Saved")
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({
    implementation_status: "partial",
    implementation_text: "Nightly Veeam jobs.",
  })
  expect(new Headers(patch.init.headers).get("X-CSRF-Token")).toBe("token-xyz")
})

test("people without write access see the description read-only", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: ["controls:read"] }),
    "GET /controls/A.8.13": () => json(200, { ...DETAIL, implementation_text: "Nightly jobs." }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByText("Nightly jobs.")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument()
})

test("an unknown control shows a helpful message", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.9.99": () => json(404, { detail: "Control not found." }),
  })
  renderApp("/controls/A.9.99")
  expect(await screen.findByRole("alert")).toHaveTextContent("Control not found.")
})

test("uploading evidence shows the checks as they run and the verdict", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  let linkPolls = 0
  let uploaded = false
  const rule = (seq: number, name: string) => ({
    seq, code: `V-${seq}`, name, status: "pass", reason: `${name} ok.`, fix_hint: null, excerpt: null,
  })
  const link = (state: string, rules: unknown[]) => ({
    id: "l1", state, confidence: state === "accepted" ? 1 : null, evidence_date: "2026-09-07",
    expires_on: "2026-10-08", slot_id: "s1", slot_name: "Backup policy", control_code: "A.8.13",
    control_title: "Information backup", artefact_id: "a1", version_id: "v1", version_no: 1,
    filename: "backup.pdf", size: 10, mime: "application/pdf", uploaded_at: "2026-10-07T09:00:00Z",
    uploaded_by: "Sana Malik", decided_by: null, decision_reason: null, rules_planned: 2, rules,
    text_preview: null,
  })
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () =>
      json(200, uploaded
        ? { ...DETAIL, slots: [{ ...DETAIL.slots[0], state: "verified", artefact: {
            link_id: "l1", version_id: "v1", filename: "backup.pdf", state: "accepted", confidence: 1,
            evidence_date: "2026-09-07", expires_on: "2026-10-08" } }] }
        : DETAIL),
    "POST /controls/A.8.13/slots/s1/artefacts": () => {
      uploaded = true
      return json(202, link("verifying", []))
    },
    "GET /artefact-links/l1": () => {
      linkPolls += 1
      return linkPolls === 1
        ? json(200, link("verifying", [rule(1, "File readable")]))
        : json(200, link("accepted", [rule(1, "File readable"), rule(2, "Document date")]))
    },
  })
  renderApp("/controls/A.8.13")
  const input = await screen.findByLabelText("Upload evidence for Backup policy")
  await userEvent.upload(input, new File(["%PDF-1.4"], "backup.pdf", { type: "application/pdf" }))
  expect(await screen.findByText("File readable")).toBeInTheDocument()
  expect(await screen.findByText(/Accepted\./, {}, { timeout: 3000 })).toBeInTheDocument()
  expect(await screen.findByText("Verified")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(post.init.body).toBeInstanceOf(FormData)
  expect(new Headers(post.init.headers).get("X-CSRF-Token")).toBe("token-xyz")
})

test("the owner attests that the control operates as described", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "POST /controls/A.8.13/attest": () =>
      json(200, { ...DETAIL, attestation: { attested_at: "2026-10-07T09:00:00Z", valid_until: "2026-11-07T09:00:00Z",
                                            by: "Sana Malik", statement: "Operates as described." } }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByText("Not attested yet")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Attest" }))
  await userEvent.click(screen.getByRole("button", { name: "Confirm attestation" }))
  expect(await screen.findByText("Attested by Sana Malik on 7 Oct 2026, valid until 7 Nov 2026")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ statement: "This control operates as described." })
})

test("the uploader can give the evidence date when the document doesn't show one clearly", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "POST /controls/A.8.13/slots/s1/artefacts": () => json(202, { id: "l1" }),
    "GET /artefact-links/l1": () => json(404, { detail: "gone" }),
  })
  renderApp("/controls/A.8.13")
  await userEvent.type(await screen.findByLabelText("Evidence date for Backup policy (optional)"), "2026-09-07")
  await userEvent.upload(
    screen.getByLabelText("Upload evidence for Backup policy"),
    new File(["%PDF-1.4"], "backup.pdf", { type: "application/pdf" }),
  )
  await vi.waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true))
  const body = calls.find((c) => c.method === "POST")!.init.body as FormData
  expect(body.get("evidence_date")).toBe("2026-09-07")
})


test("shows related ISO controls and reuses their evidence", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const ai = { ...DETAIL, code: "AI A.2.2", ref: "A.2.2", framework: "iso42001" as const, title: "AI policy", theme: "Policies related to AI",
    requirements: [{ ref: "A.2.2", title: "AI policy" }], assayr_check: null }
  const related = [{ code: "A.5.1", ref: "A.5.1", framework: "iso27001", title: "Policies for information security", status: "compliant",
    evidence: [{ version_id: "v1", filename: "policy.pdf", state: "accepted", linked: false }] }]
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/AI%20A.2.2": () => json(200, ai),
    "GET /controls/AI%20A.2.2/related": () => json(200, related),
    "POST /controls/AI%20A.2.2/reuse-evidence": () => json(200, ai),
  })
  renderApp("/controls/AI%20A.2.2")
  expect(await screen.findByRole("heading", { name: "AI policy" })).toBeInTheDocument()
  expect(screen.getAllByText("ISO/IEC 42001").length).toBeGreaterThan(0)
  expect(await screen.findByRole("link", { name: "Policies for information security" })).toHaveAttribute("href", "/controls/A.5.1")
  await userEvent.click(screen.getByRole("button", { name: "Reuse policy.pdf" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ version_id: "v1" })
})

test("shows the Assayr check and the SOC 2 test procedure", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/AI%20A.5.3": () => json(200, { ...DETAIL, code: "AI A.5.3", ref: "A.5.3", framework: "iso42001",
      title: "Documentation of AI system impact assessments",
      assayr_check: { key: "aiia_all", met: false, reason: "No approved impact assessment: AIS-001." } }),
    "GET /controls/CC6.1.1": () => json(200, { ...DETAIL, code: "CC6.1.1", ref: "CC6.1.1", framework: "soc2", title: "Invented MFA",
      test_procedure: "Inspected invented settings." }),
  })
  renderApp("/controls/AI%20A.5.3")
  expect(await screen.findByText("No approved impact assessment: AIS-001.")).toBeInTheDocument()
  expect(screen.getByText("Not met")).toBeInTheDocument()
  renderApp("/controls/CC6.1.1")
  expect(await screen.findByText("Inspected invented settings.")).toBeInTheDocument()
})
