export const LEVEL_LABEL: Record<number, string> = { 1: "Very low", 2: "Low", 3: "Medium", 4: "High", 5: "Very high" }
export const LEVEL_COLOR: Record<number, string> = {
  1: "var(--idle)",
  2: "var(--ok)",
  3: "var(--warn)",
  4: "var(--heat-4)",
  5: "var(--bad)",
}

/** A level from Very low (grey) to Very high (red): criticality, confidentiality, integrity, availability. */
export function LevelBadge({ level, testId }: { level: number; testId?: string }) {
  const color = LEVEL_COLOR[level] ?? "var(--idle)"
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-semibold"
      style={{ color, borderColor: `color-mix(in srgb, ${color} 35%, transparent)`, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
    >
      <span aria-hidden="true" className="size-1.5 rounded-full" style={{ background: color }} />
      {LEVEL_LABEL[level] ?? level}
    </span>
  )
}
