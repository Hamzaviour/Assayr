export function ProgressBar({
  value,
  max,
  label,
  color = "var(--primary)",
}: {
  value: number
  max: number
  label: string
  color?: string
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className="h-2 w-full overflow-hidden rounded-full bg-subtle"
    >
      <div
        className="grow-x h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  )
}
