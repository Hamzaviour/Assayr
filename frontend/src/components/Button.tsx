import type { ButtonHTMLAttributes } from "react"

type Variant = "primary" | "secondary" | "ghost"
type Size = "sm" | "md"

const VARIANT: Record<Variant, string> = {
  primary: "bg-primary text-on-primary border-primary hover:bg-primary-hover hover:border-primary-hover",
  secondary: "bg-surface text-fg border-line-2 hover:border-fg-3",
  ghost: "bg-transparent text-fg-2 border-transparent hover:bg-subtle",
}
const SIZE: Record<Size, string> = { sm: "px-2.5 py-1 text-[13px]", md: "px-3.5 py-2 text-sm" }

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center gap-2 whitespace-nowrap rounded-lg border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...props}
    />
  )
}
