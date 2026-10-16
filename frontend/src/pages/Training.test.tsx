import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { course } from "../test/training"
import { json, ME, mockApi, renderApp } from "../test/render"

const MANAGER = { ...ME, permissions: [...ME.permissions, "training:manage"] }

function setup() {
  document.cookie = "assayr_csrf=t; path=/"
  return mockApi({
    "GET /auth/me": () => json(200, MANAGER),
    "GET /courses": () => json(200, [course(), course({ id: "c2", title: "Induction", status: "draft", counts: { assigned: 0, passed: 0, in_progress: 0, overdue: 0, failed: 0 } })]),
    "GET /training/summary": () =>
      json(200, {
        courses: [],
        departments: [
          { department: "Finance", assigned: 10, passed: 9, completion: 90 },
          { department: "IT", assigned: 5, passed: 2, completion: 40 },
        ],
      }),
    "POST /courses": (_u, init) => json(201, course({ id: "c9", ...JSON.parse(String(init.body)), status: "draft" })),
    "GET /courses/c9": () => json(200, { ...course({ id: "c9", status: "draft" }), materials: [], assessment: null, rules: [], has_assignments: false }),
    "GET /courses/c9/assignments": () => json(200, []),
  })
}

test("course cards show completion, overdue and status", async () => {
  setup()
  renderApp("/training")
  expect(await screen.findByRole("heading", { name: "Training and awareness", level: 1 })).toBeInTheDocument()
  const card = (await screen.findByRole("link", { name: "Security awareness 2026" })).closest("li")!
  expect(within(card).getByRole("img", { name: "75% passed" })).toBeInTheDocument()
  expect(card).toHaveTextContent("5 overdue")
  expect(card).toHaveTextContent("Published")
  expect(screen.getByRole("link", { name: "Induction" }).closest("li")).toHaveTextContent("Draft")
  expect(screen.getByRole("link", { name: /Completion report/ })).toHaveAttribute("href", "/api/v1/training/report.xlsx")
  expect(screen.getByRole("link", { name: "Training" })).toHaveAttribute("aria-current", "page")
})

test("department completion is charted", async () => {
  setup()
  renderApp("/training")
  expect(await screen.findByRole("progressbar", { name: "Finance training completion" })).toHaveAttribute("aria-valuenow", "9")
})

test("New course creates a draft and opens it", async () => {
  const calls = setup()
  const { router } = renderApp("/training")
  await userEvent.click(await screen.findByRole("button", { name: "New course" }))
  await userEvent.type(screen.getByLabelText("Course title"), "Phishing basics")
  await userEvent.click(screen.getByRole("button", { name: "Create course" }))
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ title: "Phishing basics" })
  await screen.findByRole("heading", { level: 1, name: "Security awareness 2026" })
  expect(router.state.location.pathname).toBe("/training/c9")
})
