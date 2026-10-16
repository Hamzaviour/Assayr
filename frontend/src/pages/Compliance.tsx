import { Link } from "@tanstack/react-router"
import { useId, useState } from "react"
import { type FrameworkRow, type GroupRow, frameworkTitle, isNia, useDashboard } from "../api/dashboard"
import { ProgressBar } from "../components/charts"

const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value)}%`)
const ROW = "grid grid-cols-[minmax(0,180px)_minmax(0,1fr)_minmax(0,130px)] items-center gap-4 rounded-lg px-2 py-2.5"

function GroupLine({ g }: { g: GroupRow }) {
  return (
    <>
      <span className="text-[14px] font-medium">{g.name}</span>
      <ProgressBar value={g.compliant} max={g.total} label={`${g.name} controls compliant`} />
      <span className="text-right text-[13px] tabular-nums text-fg-2">
        {g.compliant} of {g.total} compliant
      </span>
    </>
  )
}

function FrameworkCard({ f }: { f: FrameworkRow }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const title = frameworkTitle(f)
  const nia = isNia(f)
  const breakdown = nia ? "Domains" : "Themes"
  return (
    <article className="grid gap-5 rounded-xl border border-line bg-surface p-6">
      <p className="flex items-baseline justify-between gap-3">
        <span className="text-[19px]">
          <strong>{title.name}</strong>
          {title.note && <span className="text-fg-3"> {title.note}</span>}
        </span>
        <span className="font-display text-[30px] font-extrabold leading-none tabular-nums text-primary">{percent(f.readiness)}</span>
      </p>
      <ProgressBar value={f.compliant} max={f.total} label={`${f.name} controls compliant`} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-fg-2">
          {f.compliant} controls compliant · {f.total} total
          {f.excluded > 0 && (
            <span className="text-fg-3">
              {" "}
              · {f.excluded} {nia ? "not applicable" : "excluded in the SoA"}
            </span>
          )}
        </p>
        {f.groups.length > 0 && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[13px] font-semibold text-primary transition-colors duration-200 hover:bg-subtle"
          >
            {breakdown}
            <span className="text-fg-3 tabular-nums">{f.groups.length}</span>
            <svg aria-hidden="true" viewBox="0 0 16 16" className={`h-3.5 w-3.5 transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
              <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
      {open && (
        <div id={panelId} role="region" aria-label={`${title.name} ${breakdown.toLowerCase()}`} className="border-t border-line pt-4">
          <ul className="grid gap-1">
            {f.groups.map((g) => (
              <li key={g.name}>
                {nia ? (
                  <div className={ROW}>
                    <GroupLine g={g} />
                  </div>
                ) : (
                  <Link to="/controls" search={{ theme: g.name }} className={`${ROW} hover:bg-subtle`}>
                    <GroupLine g={g} />
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}

export function CompliancePage() {
  const dashboard = useDashboard()
  const frameworks = dashboard.data?.frameworks ?? []
  return (
    <div className="mx-auto grid max-w-5xl gap-6">
      <header>
        <p className="mb-1 text-[13px] text-fg-3">Frameworks you are working towards</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Compliance</h1>
      </header>
      {dashboard.isError && <p role="alert">{dashboard.error.message}</p>}
      {dashboard.isPending && <div className="h-40 animate-pulse rounded-xl bg-subtle" aria-label="Loading" />}
      {frameworks.map((f) => (
        <FrameworkCard key={f.code} f={f} />
      ))}
    </div>
  )
}
