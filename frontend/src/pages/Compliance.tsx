import { Link } from "@tanstack/react-router"
import { type ReactNode, useId, useState } from "react"
import { type FrameworkRow, type GroupRow, frameworkTitle, isNia, useDashboard } from "../api/dashboard"
import { useImportNiaText } from "../api/nia"
import { useMe } from "../auth/session"
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

function NiaImport() {
  const importText = useImportNiaText()
  const result = importText.data
  return (
    <div className="grid gap-1.5 rounded-lg bg-subtle px-4 py-3">
      <label htmlFor="nia-import" className="text-[13px] font-semibold">Import official text (PDF)</label>
      <p className="text-[12.5px] text-fg-3">
        Choose your organisation's copy of the NCSA standard, version 2.1. The text stays in this installation.
      </p>
      <input
        id="nia-import"
        type="file"
        accept="application/pdf,.pdf"
        disabled={importText.isPending}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) importText.mutate(file)
          e.target.value = ""
        }}
        className="text-[13px]"
      />
      {importText.isPending && <p role="status" className="text-[12.5px] text-fg-3">Reading the document…</p>}
      {result && (
        <p role="status" className="text-[13px] font-medium text-ok">
          Matched {result.matched} controls · {result.unmatched.length} not found
        </p>
      )}
      {importText.isError && <p role="alert" className="text-[13px] text-bad">{importText.error.message}</p>}
    </div>
  )
}

/** ISO opens its controls, NIA the NIA controls, PDPPL the privacy obligations. */
function FrameworkLink({ f, className, children }: { f: FrameworkRow; className: string; children: ReactNode }) {
  if (f.code.startsWith("pdppl")) {
    return <Link to="/privacy" search={{ tab: "pdppl" }} className={className}>{children}</Link>
  }
  if (isNia(f)) {
    return <Link to="/controls" search={{ framework: "nia" }} className={className}>{children}</Link>
  }
  return <Link to="/controls" className={className}>{children}</Link>
}

function FrameworkCard({ f }: { f: FrameworkRow }) {
  const me = useMe()
  const canImport = (me.data?.permissions ?? []).includes("controls:write")
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const title = frameworkTitle(f)
  const nia = isNia(f)
  const pdppl = f.code.startsWith("pdppl")
  const breakdown = pdppl ? "Topics" : nia ? "Domains" : "Themes"
  return (
    <article className="grid gap-5 rounded-xl border border-line bg-surface p-6">
      <p className="flex items-baseline justify-between gap-3">
        <FrameworkLink f={f} className="text-[19px] hover:text-primary hover:underline">
          <strong>{title.name}</strong>
          {title.note && <span className="text-fg-3"> {title.note}</span>}
        </FrameworkLink>
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
      {nia && canImport && <NiaImport />}
      {open && (
        <div id={panelId} role="region" aria-label={`${title.name} ${breakdown.toLowerCase()}`} className="border-t border-line pt-4">
          <ul className="grid gap-1">
            {f.groups.map((g) => (
              <li key={g.name}>
                {pdppl ? (
                  <div className={ROW}>
                    <GroupLine g={g} />
                  </div>
                ) : nia ? (
                  <Link to="/controls" search={{ framework: "nia", domain: g.code ?? undefined }} className={`${ROW} hover:bg-subtle`}>
                    <GroupLine g={g} />
                  </Link>
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
