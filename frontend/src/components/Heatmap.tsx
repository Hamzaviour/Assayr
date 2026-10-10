import { Fragment } from "react"
import type { Band } from "../api/types"
import { HEAT } from "./LevelPill"

export interface HeatPoint { code: string; title: string; likelihood: number; consequence: number }
const SCALE = [1, 2, 3, 4, 5]

export function Heatmap({ points, bands, selected, onSelect, marker, size = "md" }: {
  points: HeatPoint[]
  bands: Band[]
  selected?: [number, number] | null
  onSelect?: (cell: [number, number] | null) => void
  marker?: { likelihood: number; consequence: number } | null
  size?: "sm" | "md"
}) {
  const bandOf = (score: number) => bands.find((b) => score >= b.min && score <= b.max)
  return (
    <div className="grid gap-1.5">
      <div className="grid grid-cols-[1.25rem_repeat(5,minmax(0,1fr))] gap-1" role="group" aria-label="Risk heatmap">
        {[...SCALE].reverse().map((consequence) => (
          <Fragment key={consequence}>
            <span className="flex items-center justify-end pr-1 text-[11px] text-fg-3" aria-hidden="true">{consequence}</span>
            {SCALE.map((likelihood) => {
              const count = points.filter((p) => p.likelihood === likelihood && p.consequence === consequence).length
              const band = bandOf(likelihood * consequence)
              const isSelected = selected?.[0] === likelihood && selected?.[1] === consequence
              const isMarker = marker?.likelihood === likelihood && marker?.consequence === consequence
              const label = `Likelihood ${likelihood}, consequence ${consequence}: ${count} ${count === 1 ? "risk" : "risks"}`
              const className = `relative flex aspect-square items-center justify-center rounded-md text-on-heat tabular-nums ${HEAT[band?.key ?? ""] ?? "bg-subtle"} ${isSelected ? "ring-2 ring-fg ring-offset-1 ring-offset-surface" : ""} ${size === "sm" ? "text-[11px]" : "text-sm font-semibold"}`
              const content = (
                <>
                  {count > 0 ? count : ""}
                  {isMarker && (
                    <span className="absolute size-3 rounded-full border-2 border-surface bg-ink" title="This risk" aria-hidden="true" />
                  )}
                </>
              )
              return onSelect ? (
                <button key={likelihood} type="button" aria-label={label} aria-pressed={isSelected} className={className}
                  onClick={() => onSelect(isSelected ? null : [likelihood, consequence])}>
                  {content}
                </button>
              ) : (
                <div key={likelihood} aria-label={label} className={className}>{content}</div>
              )
            })}
          </Fragment>
        ))}
        <span aria-hidden="true" />
        {SCALE.map((likelihood) => (
          <span key={likelihood} className="text-center text-[11px] text-fg-3" aria-hidden="true">{likelihood}</span>
        ))}
      </div>
      <p className="flex justify-between text-[11px] text-fg-3" aria-hidden="true">
        <span>↑ Consequence</span>
        <span>Likelihood →</span>
      </p>
    </div>
  )
}
