import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Button } from "./Button"

test("primary button calls its handler", async () => {
  const onClick = vi.fn()
  render(<Button onClick={onClick}>Upload evidence</Button>)
  await userEvent.click(screen.getByRole("button", { name: "Upload evidence" }))
  expect(onClick).toHaveBeenCalledOnce()
  expect(screen.getByRole("button")).toHaveClass("bg-primary")
})

test("disabled button ignores clicks", async () => {
  const onClick = vi.fn()
  render(<Button disabled onClick={onClick}>Save</Button>)
  await userEvent.click(screen.getByRole("button", { name: "Save" }))
  expect(onClick).not.toHaveBeenCalled()
})
