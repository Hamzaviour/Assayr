import { FRAMEWORK_LABEL } from "../api/controls"

/** A small label naming which framework a control belongs to. */
export function FrameworkChip({ framework }: { framework?: string }) {
  if (!framework) return null
  return (
    <span className="inline-flex items-center whitespace-nowrap rounded-full border border-primary/25 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold text-primary">
      {FRAMEWORK_LABEL[framework] ?? framework}
    </span>
  )
}
