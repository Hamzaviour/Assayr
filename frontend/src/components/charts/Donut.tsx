import { DataTable } from "./DataTable"
import type { Segment } from "./StackedBar"

const R = 42
const CIRCUMFERENCE = 2 * Math.PI * R

export function Donut({ segments, label, centre }: { segments: Segment[]; label: string; centre?: string }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const arcs: { s: Segment; length: number; offset: number }[] = []
  let offset = 0
  if (total > 0) {
    for (const s of segments.filter((x) => x.value > 0)) {
      const length = (s.value / total) * CIRCUMFERENCE
      arcs.push({ s, length, offset })
      offset += length
    }
  }
  return (
    <figure className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 100 100" className="size-40" role="img" aria-label={label}>
        <circle cx="50" cy="50" r={R} fill="none" stroke="var(--subtle)" strokeWidth="12" />
        {arcs.map(({ s, length, offset: start }) => (
          <circle
            key={s.key}
            cx="50"
            cy="50"
            r={R}
            fill="none"
            stroke={s.color}
            strokeWidth="12"
            strokeDasharray={`${length} ${CIRCUMFERENCE - length}`}
            strokeDashoffset={-start}
            transform="rotate(-90 50 50)"
          >
            <title>{`${s.label}: ${s.value}`}</title>
          </circle>
        ))}
        {centre && (
          <text x="50" y="55" textAnchor="middle" fill="var(--text)" fontSize="15" fontWeight="700">
            {centre}
          </text>
        )}
      </svg>
      <DataTable caption={label} rows={segments.map((s) => [s.label, String(s.value)])} />
    </figure>
  )
}
