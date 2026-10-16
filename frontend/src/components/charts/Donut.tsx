import { DataTable } from "./DataTable"
import type { Segment } from "./StackedBar"

const R = 42
const CIRCUMFERENCE = 2 * Math.PI * R

/** Keyboard and pointer activation for a chart mark that opens a filtered list. */
export function markProps(onSelect: ((key: string) => void) | undefined, key: string, name: string) {
  if (!onSelect) return {}
  return {
    role: "button",
    tabIndex: 0,
    "aria-label": name,
    onClick: () => onSelect(key),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        onSelect(key)
      }
    },
  }
}

export function Donut({
  segments,
  label,
  centre,
  onSelect,
}: {
  segments: Segment[]
  label: string
  centre?: string
  onSelect?: (key: string) => void
}) {
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
      <svg viewBox="0 0 100 100" className="size-40" role={onSelect ? "group" : "img"} aria-label={label}>
        <circle cx="50" cy="50" r={R} fill="none" stroke="var(--subtle)" strokeWidth="12" />
        <g className="spin-in">
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
            className={onSelect ? "chart-mark" : undefined}
            {...markProps(onSelect, s.key, `${s.label}: ${s.value}. Open these`)}
          >
            <title>{`${s.label}: ${s.value}`}</title>
          </circle>
        ))}
        </g>
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
