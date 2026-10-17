import { Icon } from "./icons"

/**
 * One status language for every module. Each tone pairs a colour with an icon and a word,
 * so colour is never the only cue (WCAG 1.4.1).
 */
export type Tone = "success" | "progress" | "review" | "warning" | "danger" | "neutral" | "muted"

export const TONE_CLASS: Record<Tone, string> = {
  success: "bg-ok-soft text-ok border-ok/25",
  progress: "bg-info-soft text-info border-info/25",
  review: "bg-review-soft text-review border-review/25",
  warning: "bg-warn-soft text-warn border-warn/25",
  danger: "bg-bad-soft text-bad border-bad/25",
  neutral: "bg-idle-soft text-idle border-idle/25",
  muted: "bg-transparent text-na border-line-2 border-dashed",
}
export const TONE_COLOR: Record<Tone, string> = {
  success: "var(--ok)",
  progress: "var(--info)",
  review: "var(--review)",
  warning: "var(--warn)",
  danger: "var(--bad)",
  neutral: "var(--idle)",
  muted: "var(--na)",
}
const TONE_ICON: Record<Tone, string> = {
  success: "compliant",
  progress: "in_progress",
  review: "in_review",
  warning: "at_risk",
  danger: "non_compliant",
  neutral: "not_started",
  muted: "excluded",
}

/** Every status Assayr shows, by area: [tone, label]. */
export const STATUSES = {
  control: {
    compliant: ["success", "Compliant"],
    in_progress: ["progress", "In progress"],
    in_review: ["review", "In review"],
    at_risk: ["warning", "At risk"],
    non_compliant: ["danger", "Non-compliant"],
    not_started: ["neutral", "Not started"],
    excluded: ["muted", "Excluded"],
  },
  document: {
    draft: ["neutral", "Draft"],
    approved: ["success", "Approved"],
    retired: ["muted", "Retired"],
  },
  audit: {
    draft: ["neutral", "Draft"],
    in_progress: ["progress", "In progress"],
    completed: ["success", "Completed"],
  },
  auditResult: {
    pass: ["success", "Pass"],
    partial: ["warning", "Partial"],
    fail: ["danger", "Fail"],
    na: ["muted", "NA"],
  },
  course: {
    draft: ["neutral", "Draft"],
    published: ["success", "Published"],
    archived: ["muted", "Archived"],
  },
  assignment: {
    assigned: ["neutral", "Not started"],
    in_progress: ["progress", "In progress"],
    passed: ["success", "Passed"],
    failed: ["danger", "Failed"],
  },
  activity: {
    draft: ["neutral", "Draft"],
    active: ["success", "Active"],
    retired: ["muted", "Retired"],
  },
  dpia: {
    draft: ["neutral", "Draft"],
    in_review: ["review", "In review"],
    approved: ["success", "Approved"],
  },
  request: {
    open: ["neutral", "Open"],
    in_progress: ["progress", "In progress"],
    closed: ["success", "Closed"],
  },
  breach: {
    open: ["danger", "Open"],
    contained: ["warning", "Contained"],
    closed: ["success", "Closed"],
  },
  review: {
    satisfactory: ["success", "Satisfactory"],
    concerns: ["warning", "Concerns"],
    unsatisfactory: ["danger", "Unsatisfactory"],
  },
  evidence: {
    met: ["success", "Met"],
    partial: ["warning", "Partial"],
    missing: ["danger", "Missing"],
    na: ["muted", "Shown by controls"],
  },
  aiLifecycle: {
    planned: ["neutral", "Planned"],
    development: ["progress", "Development"],
    validation: ["review", "Validation"],
    deployed: ["success", "Deployed"],
    retired: ["muted", "Retired"],
  },
  aiia: {
    draft: ["neutral", "Draft"],
    in_review: ["review", "In review"],
    approved: ["success", "Approved"],
  },
  soc2Result: {
    no_exception: ["success", "No exceptions"],
    exception: ["danger", "Exception"],
    not_tested: ["neutral", "Not tested"],
  },
  risk: {
    draft: ["neutral", "Draft"],
    assessed: ["review", "Assessed"],
    reassessing: ["review", "Reassessing"],
    treatment_planned: ["progress", "Treatment planned"],
    in_treatment: ["progress", "In treatment"],
    treated: ["success", "Treated"],
    accepted: ["success", "Accepted"],
    review_due: ["warning", "Review due"],
    closed: ["muted", "Closed"],
  },
} satisfies Record<string, Record<string, [Tone, string]>>

export type StatusArea = keyof typeof STATUSES

export function statusOf(area: StatusArea, value: string): [Tone, string] {
  const table = STATUSES[area] as Record<string, [Tone, string]>
  return table[value] ?? ["neutral", value.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase())]
}

export function Badge({ tone, label, icon = true }: { tone: Tone; label: string; icon?: boolean }) {
  return (
    <span className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border pl-[7px] pr-[9px] text-xs font-medium ${TONE_CLASS[tone]}`}>
      {icon && <Icon name={TONE_ICON[tone]} size={13} />}
      <span>{label}</span>
    </span>
  )
}

/** The badge for a status value in an area, e.g. <Status area="document" value="approved" />. */
export function Status({ area, value, label }: { area: StatusArea; value: string; label?: string }) {
  const [tone, text] = statusOf(area, value)
  return <Badge tone={tone} label={label ?? text} />
}
