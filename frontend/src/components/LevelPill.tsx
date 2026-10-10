import { RISK_STATUS_LABEL } from "../api/risks"
import type { Level } from "../api/types"
import { StatusPill } from "./StatusPill"

export const HEAT: Record<string, string> = {
  very_low: "bg-heat-1",
  low: "bg-heat-2",
  medium: "bg-heat-3",
  high: "bg-heat-4",
  critical: "bg-heat-5",
}

export function LevelPill({ level }: { level: Level | null }) {
  if (!level) return <span className="text-fg-3">—</span>
  return (
    <span
      className={`inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-semibold tabular-nums text-on-heat ${HEAT[level.band] ?? "bg-subtle"}`}
      title={`Likelihood ${level.likelihood} × consequence ${level.consequence}`}
    >
      {`${level.band_label} ${level.score}`}
    </span>
  )
}

const RISK_STYLE: Record<string, string> = {
  draft: "not_started",
  reassessing: "in_review",
  assessed: "in_progress",
  treatment_planned: "in_progress",
  in_treatment: "in_progress",
  treated: "in_review",
  accepted: "compliant",
  review_due: "at_risk",
  closed: "excluded",
}

export function RiskStatusPill({ status }: { status: string }) {
  return <StatusPill status={RISK_STYLE[status] ?? "not_started"} label={RISK_STATUS_LABEL[status] ?? status} />
}
