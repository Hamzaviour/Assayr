import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill, STATUS_LABEL } from "../components/StatusPill"

const SWATCHES = [
  ["Attest cobalt", "var(--primary)"], ["Ink", "var(--ink)"], ["Seal brass", "var(--brass)"],
  ["Compliant", "var(--ok)"], ["At risk", "var(--warn)"], ["Non-compliant", "var(--bad)"], ["In review", "var(--review)"],
] as const

export function Styleguide() {
  return (
    <div className="mx-auto grid max-w-4xl gap-10 py-2">
      <header>
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Strata design system</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Styleguide</h1>
      </header>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Colour</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SWATCHES.map(([name, value]) => (
            <div key={name} className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="h-16" style={{ background: value }} />
              <div className="px-3 py-2 text-[13px]">{name}</div>
            </div>
          ))}
        </div>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Type</h2>
        <p className="font-display text-5xl font-extrabold tracking-tight">Readiness 87%</p>
        <p className="max-w-[65ch] text-fg-2">
          This access review is dated 3 Mar 2026; reviews must fall within 90 days. Upload the latest review to keep{" "}
          <ControlId code="A.5.18" /> compliant.
        </p>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Status</h2>
        <div className="flex flex-wrap gap-2">
          {Object.keys(STATUS_LABEL).map((s) => <StatusPill key={s} status={s} />)}
        </div>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Buttons</h2>
        <div className="flex flex-wrap gap-2">
          <Button>Upload evidence</Button>
          <Button variant="secondary">Export</Button>
          <Button variant="ghost">Cancel</Button>
          <Button disabled>Saving…</Button>
        </div>
      </section>
    </div>
  )
}
