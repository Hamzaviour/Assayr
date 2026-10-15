import { DataTable } from "./DataTable"

const W = 300
const H = 120
const PAD = 6

export function LineChart({
  points,
  label,
  yMax = 100,
  format = (y) => String(y),
}: {
  points: { x: string; y: number }[]
  label: string
  yMax?: number
  format?: (y: number) => string
}) {
  const xAt = (i: number) => (points.length > 1 ? PAD + (i * (W - 2 * PAD)) / (points.length - 1) : W / 2)
  const yAt = (y: number) => H - PAD - (Math.min(y, yMax) / yMax) * (H - 2 * PAD)
  const line = points.map((p, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(p.y).toFixed(1)}`).join(" ")
  const area = points.length
    ? `${line} L${xAt(points.length - 1).toFixed(1)},${H - PAD} L${xAt(0).toFixed(1)},${H - PAD} Z`
    : ""
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-32 w-full" preserveAspectRatio="none" role="img" aria-label={label}>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--line)" strokeWidth="1" />
        ))}
        {points.length > 0 && <path d={area} fill="var(--primary-soft)" />}
        {points.length > 0 && (
          <path d={line} pathLength={1} className="draw" fill="none" stroke="var(--chart-1)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
        )}
        {points.map((p, i) => (
          <circle key={`${i}-${p.x}`} cx={xAt(i)} cy={yAt(p.y)} r="2.5" fill="var(--chart-1)">
            <title>{`${p.x}: ${format(p.y)}`}</title>
          </circle>
        ))}
      </svg>
      <DataTable caption={label} rows={points.map((p) => [p.x, format(p.y)])} />
    </figure>
  )
}
