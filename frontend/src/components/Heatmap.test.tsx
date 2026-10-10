import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { METHODOLOGY } from "../test/fixtures"
import { Heatmap } from "./Heatmap"

test("cells show how many risks sit at each position and can be selected", async () => {
  const onSelect = vi.fn()
  const points = [
    { code: "R-001", title: "a", likelihood: 4, consequence: 4 },
    { code: "R-002", title: "b", likelihood: 4, consequence: 4 },
  ]
  render(<Heatmap points={points} bands={METHODOLOGY.bands} onSelect={onSelect} />)
  const cell = screen.getByRole("button", { name: "Likelihood 4, consequence 4: 2 risks" })
  expect(cell).toHaveTextContent("2")
  expect(screen.getByRole("button", { name: "Likelihood 1, consequence 1: 0 risks" })).toHaveTextContent("")
  await userEvent.click(cell)
  expect(onSelect).toHaveBeenCalledWith([4, 4])
})
