import { screen } from "@testing-library/react"
import { myRow } from "../test/myTraining"
import { json, ME, mockApi, renderApp } from "../test/render"

test("my training lists assignments with due and overdue badges", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /my/assignments": () =>
      json(200, [
        myRow({ overdue: true, status: "in_progress", materials_done: 1 }),
        myRow({ id: "as2", course_title: "Induction", status: "passed", completed_at: "2026-10-10T09:00:00Z", best_score: 90 }),
      ]),
  })
  renderApp("/my-training")
  expect(await screen.findByRole("heading", { name: "My training", level: 1 })).toBeInTheDocument()
  const due = (await screen.findByRole("link", { name: /Security awareness 2026/ })).closest("li")!
  expect(due).toHaveTextContent("Overdue")
  expect(due).toHaveTextContent("1 of 2 materials")
  expect(screen.getByRole("link", { name: /Security awareness 2026/ })).toHaveAttribute("href", "/my-training/as1")
  expect(screen.getByRole("link", { name: /Induction/ }).closest("li")).toHaveTextContent("Passed")
  expect(screen.getByText("1 to do")).toBeInTheDocument()
})

test("nothing assigned says so", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /my/assignments": () => json(200, []) })
  renderApp("/my-training")
  expect(await screen.findByText(/no training assigned/i)).toBeInTheDocument()
})
