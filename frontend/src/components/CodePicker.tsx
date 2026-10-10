import { useState } from "react"

export function CodePicker({ label, items, selected, onChange }: {
  label: string
  items: { code: string; name: string }[]
  selected: string[]
  onChange: (codes: string[]) => void
}) {
  const [filter, setFilter] = useState("")
  const term = filter.trim().toLowerCase()
  const shown = items.filter(
    (item) => !term || selected.includes(item.code) || `${item.code} ${item.name}`.toLowerCase().includes(term),
  )
  function toggle(code: string) {
    onChange(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code])
  }
  return (
    <fieldset className="grid gap-2">
      <legend className="text-[13px] font-medium">
        {label} <span className="font-normal text-fg-3">({selected.length} selected)</span>
      </legend>
      <input aria-label={`Filter ${label.toLowerCase()}`} value={filter} onChange={(e) => setFilter(e.target.value)}
        placeholder="Type to filter" className="rounded-lg border border-line-2 bg-surface px-3 py-1.5 text-[13px]" />
      <div className="grid max-h-48 gap-1 overflow-y-auto rounded-lg border border-line p-2">
        {shown.map((item) => (
          <label key={item.code} className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={selected.includes(item.code)} onChange={() => toggle(item.code)} />
            <span className="font-mono text-fg-3">{item.code}</span> {item.name}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
