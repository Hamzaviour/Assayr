import { usePeople } from "../api/people"

type Owner = { id: string; full_name: string }

/** Choose an active person as owner; a deactivated current owner stays visible so the choice is never silent. */
export function OwnerPicker({
  value,
  current,
  onChange,
  label,
  disabled,
}: {
  value: string | null
  current?: Owner | null
  onChange: (id: string | null) => void
  label: string
  disabled?: boolean
}) {
  const people = usePeople()
  const active = people.data ?? []
  const inactive = current && !active.some((p) => p.id === current.id) && people.isSuccess ? current : null
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      disabled={disabled || people.isPending}
      onChange={(e) => onChange(e.target.value || null)}
      className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] focus-visible:outline-2 focus-visible:outline-primary"
    >
      <option value="">Unassigned</option>
      {inactive && <option value={inactive.id}>{inactive.full_name} (inactive)</option>}
      {active.map((p) => (
        <option key={p.id} value={p.id}>
          {p.full_name}
        </option>
      ))}
    </select>
  )
}
