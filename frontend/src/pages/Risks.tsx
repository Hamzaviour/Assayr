import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { RISK_STATUS_LABEL, TREATMENT_LABEL, useMethodology, useRisks } from "../api/risks"
import type { RiskRow } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { Heatmap } from "../components/Heatmap"
import { LevelPill, RiskStatusPill } from "../components/LevelPill"
import { Segmented } from "../components/Segmented"
import { formatDate } from "../lib/format"

type View = "table" | "board" | "heatmap"
type Matrix = "inherent" | "current" | "target"
const VIEWS: { key: View; label: string }[] = [
  { key: "table", label: "Table" }, { key: "board", label: "Board" }, { key: "heatmap", label: "Heatmap" },
]
const MATRICES: { key: Matrix; label: string }[] = [
  { key: "inherent", label: "Inherent" }, { key: "current", label: "Current" }, { key: "target", label: "Target" },
]
const BOARD = ["draft", "assessed", "reassessing", "treatment_planned", "in_treatment", "treated", "accepted", "review_due"]
const linkClass = "rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3"

function RiskLink({ risk }: { risk: RiskRow }) {
  return (
    <Link to="/risks/$code" params={{ code: risk.code }} className="text-fg hover:text-primary">{risk.title}</Link>
  )
}

export function RisksPage() {
  const me = useMe()
  const canCreate = me.data?.permissions.includes("risks:write") ?? false
  const [view, setView] = useState<View>("table")
  const [matrix, setMatrix] = useState<Matrix>("current")
  const [typed, setTyped] = useState("")
  const [query, setQuery] = useState("")
  const [owner, setOwner] = useState<"" | "me" | "none">("")
  const [cell, setCell] = useState<[number, number] | null>(null)
  const risks = useRisks({ q: query || undefined, owner: owner || undefined })
  const methodology = useMethodology()
  const rows = risks.data ?? []

  function onSearch(event: FormEvent) {
    event.preventDefault()
    setQuery(typed.trim())
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Risk</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Risks</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="View" options={VIEWS} value={view} onChange={setView} />
          <Link to="/risks/snapshots" className={linkClass}>Snapshots</Link>
          <a href="/api/v1/risk-register/export.xlsx" className={linkClass}>Export XLSX</a>
          {canCreate && (
            <Link to="/risks/new" className="rounded-lg bg-primary px-2.5 py-1 text-[13px] font-medium text-on-primary hover:bg-primary-hover">
              New risk
            </Link>
          )}
        </div>
      </header>
      <section className="rounded-xl border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <label className="flex items-center gap-2 text-[13px]">
            Owner
            <select
              value={owner}
              onChange={(e) => setOwner(e.target.value as "" | "me" | "none")}
              className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
            >
              <option value="">Anyone</option>
              <option value="me">Mine</option>
              <option value="none">Unassigned</option>
            </select>
          </label>
          {view === "heatmap" && <Segmented label="Matrix" options={MATRICES} value={matrix} onChange={(m) => { setMatrix(m); setCell(null) }} />}
          <form onSubmit={onSearch} className="ml-auto flex min-w-0 flex-1 justify-end gap-2" role="search">
            <label htmlFor="risk-search" className="sr-only">Search risks</label>
            <input id="risk-search" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Filter by ID or title"
              className="w-full min-w-0 max-w-72 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]" />
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
        </div>
        {risks.isError && <p role="alert" className="p-4">{risks.error.message}</p>}
        {risks.isSuccess && rows.length === 0 && (
          <p className="px-4 py-8 text-center text-fg-3">{query || owner ? "No risks match these filters." : "No risks yet."}</p>
        )}
        {rows.length > 0 && view === "table" && <RiskTable rows={rows} />}
        {rows.length > 0 && view === "board" && <RiskBoard rows={rows} />}
        {rows.length > 0 && view === "heatmap" && methodology.data && (
          <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <Heatmap
              bands={methodology.data.bands}
              selected={cell}
              onSelect={setCell}
              points={rows.flatMap((r) => {
                const lvl = r[matrix]
                return lvl ? [{ code: r.code, title: r.title, likelihood: lvl.likelihood, consequence: lvl.consequence }] : []
              })}
            />
            <section aria-label="Selected cell" className="grid content-start gap-2">
              {cell ? (
                <ul className="grid gap-2">
                  {rows.filter((r) => r[matrix]?.likelihood === cell[0] && r[matrix]?.consequence === cell[1]).map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                      <span className="min-w-0"><span className="font-mono text-[12px] text-fg-3">{r.code}</span> <RiskLink risk={r} /></span>
                      <RiskStatusPill status={r.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] text-fg-3">Select a cell to see its risks.</p>
              )}
            </section>
          </div>
        )}
      </section>
    </div>
  )
}

function RiskTable({ rows }: { rows: RiskRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
            {["ID", "Risk", "Owner", "Status", "Inherent", "Current", "Target", "Treatment", "Actions", "Next review"].map((h) => (
              <th key={h} className="px-3.5 py-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-line hover:bg-subtle">
              <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[12.5px] text-fg-3">{r.code}</td>
              <td className="min-w-60 px-3.5 py-2.5"><RiskLink risk={r} /></td>
              <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{r.owner?.full_name ?? "Unassigned"}</td>
              <td className="px-3.5 py-2.5"><RiskStatusPill status={r.status} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.inherent} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.current} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.target} /></td>
              <td className="px-3.5 py-2.5 text-fg-2">{r.treatment_option ? TREATMENT_LABEL[r.treatment_option] : "—"}</td>
              <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">
                {r.progress.total ? `${r.progress.done} of ${r.progress.total}` : "—"}
              </td>
              <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{r.review_due ? formatDate(r.review_due) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RiskBoard({ rows }: { rows: RiskRow[] }) {
  return (
    <div className="flex gap-3 overflow-x-auto p-4">
      {BOARD.map((status) => {
        const column = rows.filter((r) => r.status === status)
        return (
          <section key={status} aria-label={RISK_STATUS_LABEL[status]} className="grid w-60 shrink-0 content-start gap-2 rounded-lg bg-subtle p-2">
            <h2 className="flex justify-between px-1 text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-3">
              {RISK_STATUS_LABEL[status]} <span className="tabular-nums">{column.length}</span>
            </h2>
            {column.map((r) => (
              <article key={r.id} className="grid gap-1.5 rounded-lg border border-line bg-surface p-3">
                <span className="font-mono text-[11.5px] text-fg-3">{r.code}</span>
                <RiskLink risk={r} />
                <LevelPill level={r.current ?? r.inherent} />
              </article>
            ))}
          </section>
        )
      })}
    </div>
  )
}
