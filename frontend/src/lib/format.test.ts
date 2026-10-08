import { formatDate } from "./format"

test("dates read as day, short month, year", () => {
  expect(formatDate("2026-02-04")).toBe("4 Feb 2026")
  expect(formatDate("2026-10-07T09:30:00Z")).toBe("7 Oct 2026")
})
