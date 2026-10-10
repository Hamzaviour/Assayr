export function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string
  options: { key: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border border-line-2 bg-surface p-0.5">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          aria-pressed={value === option.key}
          onClick={() => onChange(option.key)}
          className="rounded-md px-2.5 py-1 text-[13px] font-medium text-fg-2 aria-pressed:bg-primary-soft aria-pressed:text-primary"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
