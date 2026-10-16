import { DataTable } from "./DataTable"
import { markProps } from "./Donut"
import type { Segment } from "./StackedBar"

const W = 300
const H = 120
const GAP = 12

export function BarChart({ bars, label, onSelect }: { bars: Segment[]; label: string; onSelect?: (key: string) => void }) {
  const max = Math.max(1, ...bars.map((b) => b.value))
  const width = bars.length ? (W - GAP * (bars.length + 1)) / bars.length : 0
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="h-36 w-full" role={onSelect ? "group" : "img"} aria-label={label}>
        <line x1="0" x2={W} y1={H} y2={H} stroke="var(--line)" strokeWidth="1" />
        {bars.map((b, i) => {
          const height = (b.value / max) * (H - 10)
          const x = GAP + i * (width + GAP)
          return (
            <g key={b.key}>
              <rect
                data-bar
                className={`grow-y${onSelect ? " chart-mark" : ""}`}
                style={{ "--i": i } as React.CSSProperties}
                x={x}
                y={H - height}
                width={width}
                height={height}
                rx="4"
                fill={b.color}
                {...markProps(onSelect, b.key, `${b.label}: ${b.value}. Open these`)}
              >
                <title>{`${b.label}: ${b.value}`}</title>
              </rect>
              <text x={x + width / 2} y={H + 14} textAnchor="middle" fill="var(--text-2)" fontSize="10">
                {b.label}
              </text>
            </g>
          )
        })}
      </svg>
      <DataTable caption={label} rows={bars.map((b) => [b.label, String(b.value)])} />
    </figure>
  )
}
