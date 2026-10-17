import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { useState } from "react"
import { GRADE_LABEL, type Grade, findingsExportUrl, useFindings } from "../api/findings"
import { useMe } from "../auth/session"
import { Status } from "../components/Status"
import { StatusBar } from "../components/StatusBar"
import { formatDate } from "../lib/format"
import { countBy, statusSegments } from "../lib/statusBars"

const FIELD = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] text-fg"

/** The due date, in red with the word "Overdue" once it has passed. */
export function DueDate({ due, overdue }: { due: string | null; overdue: boolean }) {
  if (!due) return <span className="text-fg-3">No date</span>
  return (
    <span className={overdue ? "font-semibold text-bad" : "text-fg-2"}>
      {formatDate(due)}
      {overdue && " · Overdue"}
    </span>
  )
}

export function FindingsPage() {
  const me = useMe()
  const findings = useFindings()
  const search = useSearch({ from: "/app/findings" })
  const navigate = useNavigate({ from: "/findings" })
  const [status, setStatus] = useState<string | null>(null)
  const [grade, setGrade] = useState("")
  const [owner, setOwner] = useState("")
  const overdue = search.overdue === true
  const all = findings.data ?? []
  const rows = all.filter(
    (f) =>
      (!status || f.status === status) &&
      (!grade || f.grade === grade) &&
      (owner === "" || (owner === "me" ? f.owner?.id === me.data?.id : !f.owner)) &&
      (!overdue || f.overdue),
  )

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Assure</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Findings</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            Nonconformities and observations from internal audits, with corrective actions tracked until they are verified.
          </p>
        </div>
        <a href={findingsExportUrl} className="inline-flex items-center rounded-lg border border-line px-3 py-1.5 text-[13px] font-semibold text-primary hover:bg-subtle">
          Export Excel
        </a>
      </header>

      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        {all.length > 0 && (
          <div className="grid gap-3 border-b border-line px-4 py-3">
            <StatusBar label="Findings by status" selected={status} onSelect={setStatus} segments={statusSegments("finding", countBy(all, (f) => f.status))} />
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-[13px] text-fg-2">
                Grade
                <select value={grade} onChange={(e) => setGrade(e.target.value)} className={FIELD}>
                  <option value="">All grades</option>
                  {(Object.keys(GRADE_LABEL) as Grade[]).map((g) => <option key={g} value={g}>{GRADE_LABEL[g]}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-[13px] text-fg-2">
                Owner
                <select value={owner} onChange={(e) => setOwner(e.target.value)} className={FIELD}>
                  <option value="">Everyone</option>
                  <option value="me">Mine</option>
                  <option value="none">Unassigned</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-[13px] text-fg-2">
                <input
                  type="checkbox"
                  checked={overdue}
                  onChange={(e) => navigate({ search: (prev) => ({ ...prev, overdue: e.target.checked || undefined }) })}
                />
                Overdue only
              </label>
            </div>
          </div>
        )}
        {findings.isError && <p role="alert" className="p-4">{findings.error.message}</p>}
        {findings.isPending && <p role="status" className="p-4 text-fg-3">Loading…</p>}
        {findings.isSuccess && all.length === 0 && (
          <p className="p-8 text-center text-fg-3">
            No findings yet. Raise findings from an internal audit: every fail, partial or SOC 2 exception can become one.
          </p>
        )}
        {all.length > 0 && rows.length === 0 && <p className="p-6 text-center text-fg-3">No findings match these filters.</p>}
        {rows.length > 0 && (
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
                {["Finding", "Title", "Grade", "Control", "Owner", "Due", "Actions done", "Status"].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.id} className="border-t border-line hover:bg-subtle">
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12.5px] font-semibold text-primary">{f.code}</td>
                  <td className="min-w-56 px-4 py-2.5">
                    <Link to="/findings/$id" params={{ id: f.id }} className="text-fg hover:text-primary">{f.title}</Link>
                  </td>
                  <td className="px-4 py-2.5"><Status area="findingGrade" value={f.grade} /></td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12.5px] text-fg-2">{f.ref ?? "—"}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{f.owner?.full_name ?? "Unassigned"}</td>
                  <td className="whitespace-nowrap px-4 py-2.5"><DueDate due={f.due_date} overdue={f.overdue} /></td>
                  <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-fg-2">
                    {f.actions_total ? `${f.actions_total - f.actions_open} of ${f.actions_total}` : "—"}
                  </td>
                  <td className="px-4 py-2.5"><Status area="finding" value={f.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
