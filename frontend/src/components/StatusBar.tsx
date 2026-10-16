import { useState } from "react"
import { TONE_COLOR, type Tone } from "./Status"

export type BarSegment = { key: string; label: string; value: number; tone?: Tone; color?: string }

/**
 * A stacked bar of statuses that filters its list: hover (or focus) a segment for its count and share,
 * click it — or its legend chip — to show only those rows; click again to show everything.
 */
export function StatusBar({
  segments,
  label,
  selected,
  onSelect,
}: {
  segments: BarSegment[]
  label: string
  selected?: string | null
  onSelect?: (key: string | null) => void
}) {
  const [hover, setHover] = useState<string | null>(null)
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const shown = segments.filter((s) => s.value > 0)
  const colorOf = (s: BarSegment) => s.color ?? TONE_COLOR[s.tone ?? "neutral"]
  const pct = (v: number) => (total ? Math.round((100 * v) / total) : 0)
  const active = segments.find((s) => s.key === (hover ?? selected))
  const toggle = (key: string) => onSelect?.(selected === key ? null : key)

  return (
    <div role="group" aria-label={label} className="grid gap-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-subtle">
        <div className="grow-x flex h-full w-full">
          {total > 0 &&
            shown.map((s) => (
              <button
                key={s.key}
                type="button"
                aria-label={`${s.label}: ${s.value} (${pct(s.value)}%)`}
                aria-pressed={selected === s.key}
                disabled={!onSelect}
                onMouseEnter={() => setHover(s.key)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(s.key)}
                onBlur={() => setHover(null)}
                onClick={() => toggle(s.key)}
                className={`h-full transition-[opacity,filter] duration-200 first:rounded-l-full last:rounded-r-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text)] ${
                  selected && selected !== s.key ? "opacity-35" : ""
                } ${onSelect ? "cursor-pointer hover:brightness-110" : "cursor-default"}`}
                style={{ width: `${(s.value / total) * 100}%`, background: colorOf(s) }}
              />
            ))}
        </div>
      </div>
      <div className="flex min-h-5 flex-wrap items-center gap-x-1 gap-y-1 text-[12.5px]">
        {segments.map((s) => (
          <button
            key={s.key}
            type="button"
            disabled={!onSelect || s.value === 0}
            aria-pressed={selected === s.key}
            onClick={() => toggle(s.key)}
            onMouseEnter={() => setHover(s.key)}
            onMouseLeave={() => setHover(null)}
            className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 transition-colors ${
              selected === s.key ? "bg-subtle font-semibold text-fg ring-1 ring-line-2" : "text-fg-2"
            } ${onSelect && s.value > 0 ? "hover:bg-subtle" : "opacity-60"}`}
          >
            <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: colorOf(s) }} />
            {s.label}
            <b className="tabular-nums text-fg">{s.value}</b>
          </button>
        ))}
        <span aria-live="polite" className="ml-auto text-[12px] text-fg-3">
          {active ? `${active.label}: ${active.value} of ${total} (${pct(active.value)}%)` : selected ? "" : `${total} in total`}
        </span>
      </div>
    </div>
  )
}
