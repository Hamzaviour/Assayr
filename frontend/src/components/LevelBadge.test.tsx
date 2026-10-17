import { render, screen } from "@testing-library/react"
import { LEVEL_COLOR, LevelBadge } from "./LevelBadge"

test("each level has its own colour and word", () => {
  render(
    <>
      {[1, 2, 3, 4, 5].map((n) => (
        <LevelBadge key={n} level={n} testId={`l${n}`} />
      ))}
    </>,
  )
  expect(screen.getByTestId("l1")).toHaveTextContent("Very low")
  expect(screen.getByTestId("l5")).toHaveTextContent("Very high")
  expect(new Set(Object.values(LEVEL_COLOR)).size).toBe(5)
  expect(screen.getByTestId("l3").getAttribute("style")).toContain(LEVEL_COLOR[3])
})
