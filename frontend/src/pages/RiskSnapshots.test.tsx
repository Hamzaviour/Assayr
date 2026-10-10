import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const snapshot = (id: string, label: string) => ({
  id, label, taken_at: "2026-10-08T09:00:00Z", taken_by: "Sana Malik", methodology_version: 1, risk_count: 3,
})

test("saves a snapshot and compares two", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /risk-snapshots": () => json(200, [snapshot("s2", "Q4 2026"), snapshot("s1", "Q3 2026")]),
    "POST /risk-snapshots": () => json(201, { ...snapshot("s3", "Q1 2027"), rows: [] }),
    "GET /risk-snapshots/compare": () => json(200, {
      base: snapshot("s1", "Q3 2026"), head: snapshot("s2", "Q4 2026"), added: ["R-004"], removed: [],
      changed: [{ code: "R-001", title: "Ransomware", changes: [{ field: "current", before: "High (16)", after: "Medium (8)" }] }],
    }),
  })
  renderApp("/risks/snapshots")
  await userEvent.type(await screen.findByLabelText("Snapshot label"), "Q1 2027")
  await userEvent.click(screen.getByRole("button", { name: "Save snapshot" }))
  await userEvent.selectOptions(screen.getByLabelText("Compare"), "s1")
  await userEvent.selectOptions(screen.getByLabelText("With"), "s2")
  expect(await screen.findByText("High (16) → Medium (8)")).toBeInTheDocument()
  expect(screen.getByText(/Added: R-004/)).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ label: "Q1 2027" })
})
