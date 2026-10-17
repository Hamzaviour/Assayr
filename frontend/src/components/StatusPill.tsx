import { Icon } from "./icons"
import { STATUSES, TONE_CLASS } from "./Status"

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

const STYLE = Object.fromEntries(
  Object.entries(STATUSES.control).map(([status, [tone]]) => [status, TONE_CLASS[tone]]),
) as Record<ControlStatus, string>

function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function StatusPill({ status, label: override }: { status: string; label?: string }) {
  const known = status in STATUS_LABEL ? (status as ControlStatus) : null
  const label = override ?? (known ? STATUS_LABEL[known] : humanize(status))
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
