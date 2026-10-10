import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useCreateSnapshot, useSnapshotCompare, useSnapshots } from "../api/risks"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"

const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"

export function RiskSnapshotsPage() {
  const me = useMe()
  const canCreate = me.data?.permissions.includes("risks:write") ?? false
  const snapshots = useSnapshots()
  const create = useCreateSnapshot()
  const [label, setLabel] = useState("")
  const [base, setBase] = useState("")
  const [head, setHead] = useState("")
  const compare = useSnapshotCompare(base, head)
  const list = snapshots.data ?? []

  async function save(event: FormEvent) {
    event.preventDefault()
    await create.mutateAsync(label.trim())
    setLabel("")
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span> Snapshots
      </nav>
      <h1 className="font-display text-[26px] font-extrabold tracking-tight">Assessment snapshots</h1>
      <p className="max-w-2xl text-[13.5px] text-fg-2">
        A snapshot freezes every risk's levels and status. Keep one after each assessment as the clause 8.2 record.
      </p>
      {canCreate && (
        <form onSubmit={save} className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface p-4">
          <div className="grid min-w-56 flex-1 gap-1">
            <label htmlFor="snapshot-label" className="text-[13px] font-medium">Snapshot label</label>
            <input id="snapshot-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Q4 2026 risk assessment" className={input} />
          </div>
          <Button type="submit" disabled={!label.trim() || create.isPending}>Save snapshot</Button>
          {create.isError && <p role="alert" className="w-full text-[13px] text-bad">{create.error.message}</p>}
        </form>
      )}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["Label", "Taken", "By", "Risks"].map((h) => <th key={h} className="px-3.5 py-3 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.id} className="border-t border-line">
                <td className="px-3.5 py-2.5 font-medium">{s.label}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{formatDate(s.taken_at)}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{s.taken_by ?? "—"}</td>
                <td className="px-3.5 py-2.5 tabular-nums text-fg-2">{s.risk_count}</td>
              </tr>
            ))}
            {snapshots.isSuccess && list.length === 0 && (
              <tr><td colSpan={4} className="px-3.5 py-8 text-center text-fg-3">No snapshots yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
      {list.length >= 2 && (
        <section className="grid gap-3 rounded-xl border border-line bg-surface p-4" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="text-[15px] font-semibold">Compare snapshots</h2>
          <div className="flex flex-wrap gap-3">
            {([["Compare", base, setBase], ["With", head, setHead]] as const).map(([name, value, setter]) => (
              <div key={name} className="grid gap-1">
                <label htmlFor={`snapshot-${name}`} className="text-[13px] font-medium">{name}</label>
                <select id={`snapshot-${name}`} value={value} onChange={(e) => setter(e.target.value)} className={input}>
                  <option value="">Choose…</option>
                  {list.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            ))}
          </div>
          {compare.isError && <p role="alert">{compare.error.message}</p>}
          {compare.data && (
            <div className="grid gap-2 text-[13px]">
              {compare.data.added.length > 0 && <p>Added: {compare.data.added.join(", ")}</p>}
              {compare.data.removed.length > 0 && <p>Removed: {compare.data.removed.join(", ")}</p>}
              {compare.data.changed.length === 0 && <p className="text-fg-3">No risk changed level, status or treatment.</p>}
              <ul className="grid gap-1.5">
                {compare.data.changed.flatMap((risk) =>
                  risk.changes.map((change) => (
                    <li key={`${risk.code}-${change.field}`} className="flex flex-wrap gap-2">
                      <span className="font-mono text-fg-3">{risk.code}</span>
                      <span>{risk.title}</span>
                      <span className="text-fg-3">{change.field}</span>
                      <span>{`${change.before ?? "—"} → ${change.after ?? "—"}`}</span>
                    </li>
                  )),
                )}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
