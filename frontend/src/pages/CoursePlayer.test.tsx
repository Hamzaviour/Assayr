import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { MyAssignmentDetail } from "../api/training"
import { myDetail } from "../test/myTraining"
import { json, ME, mockApi, renderApp } from "../test/render"

function setup(detail: MyAssignmentDetail = myDetail(), result = { score: 66.7, passed: false, wrong: ["q2"], attempts_left: 2 }) {
  document.cookie = "assayr_csrf=t; path=/"
  let current = detail
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /my/assignments/as1": () => json(200, current),
    "GET /my/assignments": () => json(200, [current]),
    "POST /my/assignments/as1/materials/m1/done": () => {
      current = { ...current, done: [...current.done, "m1"] }
      return json(200, current)
    },
    "POST /my/assignments/as1/attempts": () => json(200, result),
  })
  renderApp("/my-training/as1")
  return calls
}

test("materials play in order and the assessment waits for them", async () => {
  const calls = setup()
  expect(await screen.findByRole("heading", { name: "Security awareness 2026", level: 1 })).toBeInTheDocument()
  expect(screen.getByTitle("Phishing video")).toHaveAttribute("src", "https://drive.google.com/file/d/1AbC/preview")
  const video = document.querySelector("video")!
  expect(video).toHaveAttribute("src", "/api/v1/my/assignments/as1/materials/m2/file")
  expect(screen.getByRole("link", { name: /Open Handbook/ })).toHaveAttribute("href", "/api/v1/my/assignments/as1/materials/m3/file")
  expect(screen.getByText(/Finish all 3 materials to unlock the assessment/)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Submit answers" })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "I have watched Phishing video" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/materials/m1/done"))).toBe(true)
  expect(await screen.findByText("Done")).toBeInTheDocument()
})

test("the uploaded video unlocks its confirmation when it ends", async () => {
  setup()
  const confirm = await screen.findByRole("button", { name: "I have watched Intro video" })
  expect(confirm).toBeDisabled()
  document.querySelector("video")!.dispatchEvent(new Event("ended"))
  expect(await screen.findByRole("button", { name: "I have watched Intro video" })).toBeEnabled()
})

test("answering and seeing the result", async () => {
  const calls = setup(myDetail({ done: ["m1", "m2", "m3"], assessment_locked: false, status: "in_progress" }))
  const form = await screen.findByRole("form", { name: "Assessment" })
  await userEvent.click(within(form).getByRole("radio", { name: "Right" }))
  await userEvent.click(within(form).getByRole("checkbox", { name: "A" }))
  await userEvent.click(within(form).getByRole("radio", { name: "False" }))
  expect(within(form).getByText("3 of 3 answered")).toBeInTheDocument()
  await userEvent.click(within(form).getByRole("button", { name: "Submit answers" }))
  const post = calls.find((c) => c.url.pathname.endsWith("/attempts"))!
  expect(JSON.parse(String(post.init.body))).toEqual({ answers: { q1: ["o1"], q2: ["o3"], q3: ["o7"] } })
  const result = await screen.findByRole("region", { name: "Your result" })
  expect(result).toHaveTextContent("67%")
  expect(result).toHaveTextContent("Not passed yet")
  expect(result).toHaveTextContent("1 question to review")
  expect(within(result).getByRole("button", { name: "Try again (2 attempts left)" })).toBeInTheDocument()
})

test("passing shows congratulations and no retry", async () => {
  setup(myDetail({ done: ["m1", "m2", "m3"], assessment_locked: false }), { score: 100, passed: true, wrong: [], attempts_left: 2 })
  const form = await screen.findByRole("form", { name: "Assessment" })
  await userEvent.click(within(form).getByRole("radio", { name: "Right" }))
  await userEvent.click(within(form).getByRole("checkbox", { name: "A" }))
  await userEvent.click(within(form).getByRole("radio", { name: "False" }))
  await userEvent.click(within(form).getByRole("button", { name: "Submit answers" }))
  const result = await screen.findByRole("region", { name: "Your result" })
  expect(result).toHaveTextContent("Passed")
  expect(within(result).queryByRole("button", { name: /Try again/ })).not.toBeInTheDocument()
})

test("out of attempts says who to ask", async () => {
  setup(myDetail({ done: ["m1", "m2", "m3"], assessment_locked: false, status: "failed", attempts_left: 0, attempts_used: 3 }))
  expect(await screen.findByText(/used all your attempts/i)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Submit answers" })).not.toBeInTheDocument()
})
