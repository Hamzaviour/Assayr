import { DataTable } from "./DataTable"

export type Segment = { key: string; label: string; value: number; color: string }

export function StackedBar({ segments, label }: { segments: Segment[]; label: string }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  return (
    <div>
      <div role="img" aria-label={label} className="flex h-3 w-full overflow-hidden rounded-full bg-subtle">
        <div className="grow-x flex h-full w-full">
        {total > 0 &&
          segments
            .filter((s) => s.value > 0)
            .map((s) => (
              <div
                key={s.key}
                title={`${s.label}: ${s.value}`}
                style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
              />
            ))}
        </div>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px] text-fg-2" aria-hidden="true">
        {segments.map((s) => (
          <li key={s.key} className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
            <b className="tabular-nums text-fg">{s.value}</b>
          </li>
        ))}
      </ul>
      <DataTable caption={label} rows={segments.map((s) => [s.label, String(s.value)])} />
    </div>
  )
}
