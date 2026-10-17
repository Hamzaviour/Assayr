import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { finding } from "../test/findings"
import { json, ME, mockApi, renderApp } from "../test/render"

const LIST = [
  finding(),
  finding({ id: "f2", code: "F-002", title: "CC6.1: Exception", grade: "minor", status: "open", framework: "soc2", ref: "CC6.1",
    owner: null, overdue: true, due_date: "2026-10-01", actions_open: 0, actions_total: 0 }),
  finding({ id: "f3", code: "F-003", title: "Invented observation", grade: "observation", status: "closed", owner: { id: ME.id, full_name: ME.full_name } }),
]

function setup() {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /findings": () => json(200, LIST) })
}

test("the register lists findings with grade, status, owner and due date", async () => {
  setup()
  renderApp("/findings")
  expect(await screen.findByRole("heading", { name: "Findings", level: 1 })).toBeInTheDocument()
  const row = (await screen.findByRole("link", { name: "A.5.1: Fail" })).closest("tr")!
  expect(row).toHaveTextContent("F-001")
  expect(row).toHaveTextContent("Major NC")
  expect(row).toHaveTextContent("Action planned")
  expect(row).toHaveTextContent("Omar Owner")
  expect(row).toHaveTextContent("0 of 1")
  expect(screen.getByRole("link", { name: "A.5.1: Fail" })).toHaveAttribute("href", "/findings/f1")
  const late = screen.getByRole("link", { name: "CC6.1: Exception" }).closest("tr")!
  expect(late).toHaveTextContent("Unassigned")
  expect(within(late).getByText(/Overdue/)).toBeInTheDocument()
  expect(screen.getByRole("link", { name: /Export Excel/ })).toHaveAttribute("href", "/api/v1/findings/export.xlsx")
  expect(screen.getByRole("link", { name: "Findings" })).toHaveAttribute("aria-current", "page")
})

test("filters: status bar, grade, mine and overdue", async () => {
  setup()
  renderApp("/findings")
  await screen.findByText("A.5.1: Fail")
  await userEvent.click(screen.getByRole("button", { name: /Closed: 1/ }))
  expect(screen.queryByText("A.5.1: Fail")).not.toBeInTheDocument()
  expect(screen.getByText("Invented observation")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: /Closed: 1/ }))
  await userEvent.selectOptions(screen.getByLabelText("Grade"), "minor")
  expect(screen.getAllByRole("row")).toHaveLength(2)
  await userEvent.selectOptions(screen.getByLabelText("Grade"), "")
  await userEvent.selectOptions(screen.getByLabelText("Owner"), "me")
  expect(screen.getByText("Invented observation")).toBeInTheDocument()
  expect(screen.queryByText("A.5.1: Fail")).not.toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText("Owner"), "")
  await userEvent.click(screen.getByRole("checkbox", { name: "Overdue only" }))
  expect(screen.getByText("CC6.1: Exception")).toBeInTheDocument()
  expect(screen.queryByText("A.5.1: Fail")).not.toBeInTheDocument()
})

test("the overdue link from the dashboard opens the filtered register", async () => {
  setup()
  renderApp("/findings?overdue=true")
  expect(await screen.findByText("CC6.1: Exception")).toBeInTheDocument()
  expect(screen.queryByText("A.5.1: Fail")).not.toBeInTheDocument()
  expect(screen.getByRole("checkbox", { name: "Overdue only" })).toBeChecked()
})

test("an empty register explains where findings come from", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /findings": () => json(200, []) })
  renderApp("/findings")
  expect(await screen.findByText(/raise findings from an internal audit/i)).toBeInTheDocument()
})
