import { safeNext } from "./session"

test.each([
  [undefined, "/"],
  ["/controls?theme=People", "/controls?theme=People"],
  ["//evil.com", "/"],
  ["https://evil.com/x", "/"],
  ["/\\evil.com", "/"],
  ["javascript:alert(1)", "/"],
  ["/login?next=/x", "/"],
])("safeNext(%s) -> %s", (input, expected) => {
  expect(safeNext(input)).toBe(expected)
})
