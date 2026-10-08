import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ITEM = {
  link_id: "l1", control_code: "A.7.4", control_title: "Physical security monitoring",
  slot_name: "CCTV system status", filename: "cctv.png", confidence: null, uploaded_by: "Bilal Khan",
  uploaded_at: "2026-10-07T09:00:00Z",
}
const LINK = {
  id: "l1", state: "in_review", confidence: null, evidence_date: null, expires_on: null, slot_id: "s1",
  slot_name: "CCTV system status", control_code: "A.7.4", control_title: "Physical security monitoring",
  artefact_id: "a1", version_id: "v1", version_no: 1, filename: "cctv.png", size: 10, mime: "image/png",
  uploaded_at: "2026-10-07T09:00:00Z", uploaded_by: "Bilal Khan", decided_by: null, decision_reason: null,
  rules_planned: 1,
  rules: [{ seq: 1, code: "V-SCREENSHOT", name: "Screenshot provenance", status: "skipped",
            reason: "Needs text recognition (OCR), which isn't enabled yet.", fix_hint: null, excerpt: null }],
  text_preview: null,
}

test("a reviewer accepts an item with a reason", async () => {
  let decided = false
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /review-queue": () => json(200, decided ? [] : [ITEM]),
    "GET /artefact-links/l1": () => json(200, LINK),
    "POST /artefact-links/l1/decision": () => {
      decided = true
      return json(200, { ...LINK, state: "accepted", decided_by: "Sana Malik" })
    },
  })
  renderApp("/evidence")
  expect(await screen.findByText("Screenshot provenance")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "Download cctv.png" })).toHaveAttribute(
    "href", "/api/v1/artefact-versions/v1/download")
  await userEvent.type(screen.getByLabelText("Reason"), "Timestamp visible in the photo.")
  await userEvent.click(screen.getByRole("button", { name: "Accept" }))
  expect(await screen.findByText("The review queue is clear.")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ decision: "accept", reason: "Timestamp visible in the photo." })
})

test("the server's refusal is shown", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /review-queue": () => json(200, [ITEM]),
    "GET /artefact-links/l1": () => json(200, LINK),
    "POST /artefact-links/l1/decision": () =>
      json(403, { detail: "You can't review evidence you uploaded. Ask another reviewer." }),
  })
  renderApp("/evidence")
  await userEvent.click(await screen.findByRole("button", { name: "Accept" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("You can't review evidence you uploaded.")
})
