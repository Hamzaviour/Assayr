import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { CourseDetail } from "../api/training"
import { assignmentRow, courseDetail } from "../test/training"
import { json, ME, mockApi, renderApp } from "../test/render"

const MANAGER = { ...ME, permissions: [...ME.permissions, "training:manage"] }

function setup(detail: CourseDetail = courseDetail(), rows = [assignmentRow()]) {
  document.cookie = "assayr_csrf=t; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, MANAGER),
    "GET /courses/c1": () => json(200, detail),
    "GET /courses/c1/assignments": () => json(200, rows),
    "GET /people": () => json(200, [{ id: "u2", full_name: "Omar Ali", email: "omar@acme.com" }]),
    "POST /courses/c1/materials/drive": () => json(201, detail.materials[0]),
    "POST /courses/c1/materials/file": () => json(201, detail.materials[1]),
    "PATCH /courses/c1/materials/m2": () => json(200, detail),
    "PUT /courses/c1/assessment": () => json(200, null),
    "POST /courses/c1/publish": () => json(200, { ...detail, status: "published" }),
    "POST /courses/c1/assign": () => json(200, { created: 12 }),
    "POST /assignments/as1/attempts": () => json(200, assignmentRow({ status: "in_progress" })),
  })
  renderApp("/training/c1")
  return calls
}

const last = (calls: ReturnType<typeof setup>, method: string, end: string) =>
  calls.filter((c) => c.method === method && c.url.pathname.endsWith(end)).at(-1)!

test("adding a Drive link and uploading a file", async () => {
  const calls = setup()
  const materials = await screen.findByRole("region", { name: "Materials" })
  expect(within(materials).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    expect.stringContaining("Phishing video"),
    expect.stringContaining("Handbook"),
  ])
  await userEvent.type(within(materials).getByLabelText("Title"), "Passwords video")
  await userEvent.type(within(materials).getByLabelText("Google Drive link"), "https://drive.google.com/file/d/1XyZ/view")
  await userEvent.click(within(materials).getByRole("button", { name: "Add link" }))
  expect(JSON.parse(String(last(calls, "POST", "/drive").init.body))).toEqual({ title: "Passwords video", url: "https://drive.google.com/file/d/1XyZ/view" })
  const file = new File(["%PDF-1.4"], "guide.pdf", { type: "application/pdf" })
  await userEvent.upload(within(materials).getByLabelText("Upload a file"), file)
  const form = last(calls, "POST", "/file").init.body as FormData
  expect(form.get("title")).toBe("guide")
  await userEvent.click(within(materials).getByRole("button", { name: "Move Handbook up" }))
  expect(JSON.parse(String(last(calls, "PATCH", "/m2").init.body))).toEqual({ sort_order: 0 })
})

test("building the assessment", async () => {
  const calls = setup()
  const editor = await screen.findByRole("region", { name: "Assessment" })
  await userEvent.click(within(editor).getByRole("button", { name: "Add question" }))
  await userEvent.type(within(editor).getByLabelText("Question 1"), "Invented question?")
  await userEvent.type(within(editor).getByLabelText("Question 1 option 1"), "Right")
  await userEvent.type(within(editor).getByLabelText("Question 1 option 2"), "Wrong")
  await userEvent.click(within(editor).getByLabelText("Question 1 option 1 is correct"))
  await userEvent.click(within(editor).getByRole("button", { name: "Add question" }))
  await userEvent.selectOptions(within(editor).getByLabelText("Question 2 type"), "true_false")
  await userEvent.type(within(editor).getByLabelText("Question 2"), "Invented statement.")
  await userEvent.click(within(editor).getByLabelText("Question 2 option 2 is correct"))
  await userEvent.clear(within(editor).getByLabelText("Pass mark (%)"))
  await userEvent.type(within(editor).getByLabelText("Pass mark (%)"), "70")
  await userEvent.click(within(editor).getByRole("button", { name: "Save assessment" }))
  expect(JSON.parse(String(last(calls, "PUT", "/assessment").init.body))).toEqual({
    pass_mark: 70,
    max_attempts: 3,
    shuffle: true,
    questions: [
      { kind: "single", text: "Invented question?", options: [{ text: "Right", is_correct: true }, { text: "Wrong", is_correct: false }] },
      { kind: "true_false", text: "Invented statement.", options: [{ text: "True", is_correct: false }, { text: "False", is_correct: true }] },
    ],
  })
})

test("publish and assign to a department", async () => {
  const calls = setup()
  await userEvent.click(await screen.findByRole("button", { name: "Publish" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/publish"))).toBe(true)
  const panel = screen.getByRole("region", { name: "Assign" })
  await userEvent.selectOptions(within(panel).getByLabelText("Assign to"), "department")
  await userEvent.type(within(panel).getByLabelText("Department"), "Finance")
  await userEvent.click(within(panel).getByRole("button", { name: "Assign course" }))
  expect(JSON.parse(String(last(calls, "POST", "/assign").init.body))).toEqual({ department: "Finance", due_days: 30 })
  expect(await within(panel).findByText("Assigned to 12 people.")).toBeInTheDocument()
})

test("publish needs a material", async () => {
  setup(courseDetail({ materials: [] }))
  expect(await screen.findByRole("button", { name: "Publish" })).toBeDisabled()
})

test("people table filters and granting attempts needs a reason", async () => {
  const calls = setup(courseDetail({ status: "published" }), [
    assignmentRow(),
    assignmentRow({ id: "as2", full_name: "Nadia Noor", email: "nadia@acme.com", status: "passed", best_score: 90 }),
  ])
  const people = await screen.findByRole("region", { name: "People" })
  await within(people).findByText("Nadia Noor")
  await userEvent.click(within(people).getByRole("button", { name: "Failed" }))
  expect(within(people).queryByText("Nadia Noor")).not.toBeInTheDocument()
  await userEvent.click(within(people).getByRole("button", { name: "Grant attempt to Omar Ali" }))
  const confirm = within(people).getByRole("button", { name: "Grant" })
  expect(confirm).toBeDisabled()
  await userEvent.type(within(people).getByLabelText("Reason"), "Retrained in person")
  await userEvent.click(confirm)
  expect(JSON.parse(String(last(calls, "POST", "/attempts").init.body))).toEqual({ extra: 1, reason: "Retrained in person" })
})

test("a course people are taking is locked", async () => {
  setup(courseDetail({ status: "published", has_assignments: true }))
  const materials = await screen.findByRole("region", { name: "Materials" })
  expect(within(materials).queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument()
  expect(screen.getByText(/People are taking this course/)).toBeInTheDocument()
})
