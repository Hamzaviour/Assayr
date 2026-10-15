import { render, screen } from "@testing-library/react"
import { BarChart, Donut, LineChart, ProgressBar, StackedBar } from "."

const segs = [
  { key: "a", label: "Compliant", value: 3, color: "var(--ok)" },
  { key: "b", label: "In progress", value: 1, color: "var(--warn)" },
]

test("progress bar exposes its value", () => {
  render(<ProgressBar value={43} max={93} label="ISO 27001 controls compliant" />)
  expect(screen.getByRole("progressbar", { name: "ISO 27001 controls compliant" })).toHaveAttribute("aria-valuenow", "43")
})

test("zero totals do not produce NaN", () => {
  const { container } = render(<StackedBar segments={segs.map((s) => ({ ...s, value: 0 }))} label="Empty" />)
  expect(container.innerHTML).not.toMatch(/NaN/)
  const donut = render(<Donut segments={segs.map((s) => ({ ...s, value: 0 }))} label="Empty donut" />)
  expect(donut.container.innerHTML).not.toMatch(/NaN/)
  const bar = render(<ProgressBar value={0} max={0} label="Nothing yet" />)
  expect(bar.container.innerHTML).not.toMatch(/NaN|Infinity/)
})

test("each chart has a text alternative table", () => {
  render(<Donut segments={segs} label="Control status" centre="75%" />)
  expect(screen.getByRole("img", { name: "Control status" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "Compliant" }).nextSibling).toHaveTextContent("3")
})

test("line chart lists every point", () => {
  render(
    <LineChart
      points={[{ x: "2026-10-01", y: 10 }, { x: "2026-10-15", y: 24.5 }]}
      label="Readiness trend"
      format={(y) => `${y}%`}
    />,
  )
  expect(screen.getByRole("cell", { name: "2026-10-15" }).nextSibling).toHaveTextContent("24.5%")
})

test("bar chart renders a bar per segment", () => {
  const { container } = render(<BarChart bars={segs} label="Risks by level" />)
  expect(container.querySelectorAll("rect[data-bar]")).toHaveLength(2)
})
