import { render, screen } from "@testing-library/react"
import { StatusPill } from "./StatusPill"

test("shows the label with a decorative icon", () => {
  render(<StatusPill status="at_risk" />)
  const pill = screen.getByText("At risk")
  expect(pill.parentElement?.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
})

test("every known status has a human label", () => {
  const { container } = render(
    <>
      {["not_started", "in_progress", "in_review", "at_risk", "non_compliant", "compliant", "excluded"].map((s) => (
        <StatusPill key={s} status={s} />
      ))}
    </>,
  )
  expect(container.textContent).toBe(
    "Not startedIn progressIn reviewAt riskNon-compliantCompliantExcluded",
  )
})

test("unknown statuses from a newer server still render readably", () => {
  render(<StatusPill status="awaiting_magic" />)
  expect(screen.getByText("Awaiting magic")).toBeInTheDocument()
})
