import { Icon } from "./icons"

export type ControlStatus =
  | "not_started" | "in_progress" | "in_review" | "at_risk" | "non_compliant" | "compliant" | "excluded"

export const STATUS_LABEL: Record<ControlStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  in_review: "In review",
  at_risk: "At risk",
  non_compliant: "Non-compliant",
  compliant: "Compliant",
  excluded: "Excluded",
}

const STYLE: Record<ControlStatus, string> = {
  compliant: "bg-ok-soft text-ok border-ok/25",
  at_risk: "bg-warn-soft text-warn border-warn/25",
  non_compliant: "bg-bad-soft text-bad border-bad/25",
  in_review: "bg-review-soft text-review border-review/25",
  in_progress: "bg-primary-soft text-primary border-primary/25",
  not_started: "bg-idle-soft text-idle border-idle/25",
  excluded: "bg-transparent text-na border-line-2 border-dashed",
}

function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function StatusPill({ status }: { status: string }) {
  const known = status in STATUS_LABEL ? (status as ControlStatus) : null
  const label = known ? STATUS_LABEL[known] : humanize(status)
  const style = known ? STYLE[known] : STYLE.not_started
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border pl-[7px] pr-[9px] text-xs font-medium ${style}`}
    >
      <Icon name={known ?? "not_started"} size={14} />
      <span>{label}</span>
    </span>
  )
}
