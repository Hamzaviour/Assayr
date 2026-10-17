import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { Status, STATUSES, TONE_COLOR } from "./Status"
import { StatusBar } from "./StatusBar"

function Harness() {
  const [selected, setSelected] = useState<string | null>(null)
  return (
    <>
      <StatusBar
        label="Controls by status"
        selected={selected}
        onSelect={setSelected}
        segments={[
          { key: "compliant", label: "Compliant", value: 30, tone: "success" },
          { key: "in_progress", label: "In progress", value: 10, tone: "progress" },
          { key: "non_compliant", label: "Non-compliant", value: 0, tone: "danger" },
        ]}
      />
      <p>selected: {selected ?? "none"}</p>
    </>
  )
}

test("segments show their share and filter on click", async () => {
  render(<Harness />)
  const bar = screen.getByRole("group", { name: "Controls by status" })
  expect(bar).toHaveTextContent("40 in total")
  const compliant = screen.getByRole("button", { name: "Compliant: 30 (75%)" })
  expect(compliant.getAttribute("style")).toContain(TONE_COLOR.success)
  await userEvent.hover(compliant)
  expect(bar).toHaveTextContent("Compliant: 30 of 40 (75%)")
  await userEvent.click(compliant)
  expect(screen.getByText("selected: compliant")).toBeInTheDocument()
  expect(compliant).toHaveAttribute("aria-pressed", "true")
  await userEvent.click(screen.getByRole("button", { name: /^Compliant\s*30$/ }))
  expect(screen.getByText("selected: none")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /^Non-compliant/ })).toBeDisabled()
})

test("every status area maps to a tone, a label and an icon", () => {
  render(<Status area="control" value="in_progress" />)
  expect(screen.getByText("In progress").parentElement?.className).toContain("text-info")
  for (const [area, table] of Object.entries(STATUSES)) {
    for (const [value, [tone, label]] of Object.entries(table)) {
      expect(tone, `${area}.${value}`).toBeTruthy()
      expect(label, `${area}.${value}`).toBeTruthy()
    }
  }
})
