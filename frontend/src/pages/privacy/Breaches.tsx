import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { type Breach, NOTIFY, useBreaches, useCreateBreach } from "../../api/privacy2"
import { Button } from "../../components/Button"
import { LEVEL_COLOR } from "../../components/LevelBadge"
import { formatDate } from "../../lib/format"
import { Tag } from "../Privacy"
import { Status } from "../../components/Status"
import { StatusBar } from "../../components/StatusBar"
import { countBy, statusSegments } from "../../lib/statusBars"

const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
export const SEVERITY: Record<Breach["severity"], string> = { low: "Low", medium: "Medium", high: "High", critical: "Critical" }
export const BREACH_STATUS: Record<Breach["status"], [string, string]> = {
  open: ["Open", "bg-bad-soft text-bad border-bad/25"],
  contained: ["Contained", "bg-warn-soft text-warn border-warn/25"],
  closed: ["Closed", "bg-ok-soft text-ok border-ok/25"],
}

export function SeverityBadge({ b }: { b: Pick<Breach, "severity" | "severity_level"> }) {
  const color = LEVEL_COLOR[b.severity_level]
  return (
    <span
      className="inline-flex rounded-full border px-2 py-0.5 text-[11.5px] font-semibold"
      style={{ color, borderColor: `color-mix(in srgb, ${color} 35%, transparent)`, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
    >
      {SEVERITY[b.severity]}
    </span>
  )
}

export function NotifyBadge({ b }: { b: Pick<Breach, "notification_overdue" | "hours_left" | "pending_notifications"> }) {
  if (b.notification_overdue) return <Tag tone="bg-bad text-white border-bad">Notification overdue</Tag>
  if (b.hours_left !== null && b.pending_notifications.length > 0) {
    return <Tag tone={b.hours_left <= 24 ? "bg-warn text-white border-warn" : "bg-warn-soft text-warn border-warn/25"}>{b.hours_left} h left to notify</Tag>
  }
  return <Tag tone="bg-subtle text-fg-2 border-line">No notification pending</Tag>
}

function NewBreach({ onClose }: { onClose: () => void }) {
  const create = useCreateBreach()
  const [form, setForm] = useState({ title: "", severity: "medium", regulator_notify: "undecided", people_notify: "undecided", people_affected: "" })
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      {
        title: form.title.trim(),
        discovered_at: new Date().toISOString(),
        severity: form.severity,
        regulator_notify: form.regulator_notify,
        people_notify: form.people_notify,
        people_affected: form.people_affected ? Number(form.people_affected) : null,
      },
      { onSuccess: onClose },
    )
  }
  return (
    <div role="dialog" aria-label="Record a personal data breach" className="rise m-4 rounded-2xl border border-bad/30 bg-surface p-5">
      <h2 className="mb-3 text-[15px] font-semibold">Record a personal data breach</h2>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-3">
        <label className={`${LABEL} md:col-span-3`}>
          What happened
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={300} className={FIELD} />
        </label>
        <label className={LABEL}>
          Severity
          <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} className={FIELD}>
            {Object.entries(SEVERITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Notify the authority
          <select value={form.regulator_notify} onChange={(e) => setForm({ ...form, regulator_notify: e.target.value })} className={FIELD}>
            {Object.entries(NOTIFY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Notify the people affected
          <select value={form.people_notify} onChange={(e) => setForm({ ...form, people_notify: e.target.value })} className={FIELD}>
            {Object.entries(NOTIFY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          People affected (approx.)
          <input type="number" min={0} value={form.people_affected} onChange={(e) => setForm({ ...form, people_affected: e.target.value })} className={FIELD} />
        </label>
        <p className="self-end text-[12px] text-fg-3 md:col-span-2">Discovered now. The notification clock (72 hours by default) starts from discovery.</p>
        <div className="flex items-center gap-2 md:col-span-3">
          <Button type="submit" size="sm" disabled={!form.title.trim() || create.isPending}>Record breach</Button>
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
          {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
        </div>
      </form>
    </div>
  )
}

export function Breaches({ canManage }: { canManage: boolean }) {
  const breaches = useBreaches()
  const [creating, setCreating] = useState(false)
  const all = breaches.data ?? []
  const [status, setStatus] = useState<string | null>(null)
  const rows = status ? all.filter((x) => x.status === status) : all
  return (
    <div>
      {canManage && !creating && (
        <div className="flex justify-end px-4 pt-3">
          <Button size="sm" onClick={() => setCreating(true)}>Record breach</Button>
        </div>
      )}
      {creating && <NewBreach onClose={() => setCreating(false)} />}
      {breaches.isError && <p role="alert" className="p-4">{breaches.error.message}</p>}
      {breaches.isSuccess && rows.length === 0 && <p className="p-8 text-center text-fg-3">No breaches recorded.</p>}
      {all.length > 0 && (
        <div className="border-b border-line px-4 py-3">
          <StatusBar label="Breaches by status" selected={status} onSelect={setStatus} segments={statusSegments("breach", countBy(all, (x) => x.status))} />
        </div>
      )}
      {rows.length > 0 && (
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["Breach", "What happened", "Discovered", "Severity", "Notification", "Status"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id} className={`border-t border-line hover:bg-subtle ${b.notification_overdue ? "bg-bad-soft/40" : ""}`}>
                <td className="px-4 py-2.5">
                  <Link to="/privacy/breaches/$id" params={{ id: b.id }} className="font-mono text-[12.5px] font-semibold text-primary hover:underline">
                    {b.code}
                  </Link>
                </td>
                <td className="min-w-56 px-4 py-2.5">{b.title}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{formatDate(b.discovered_at)}</td>
                <td className="px-4 py-2.5"><SeverityBadge b={b} /></td>
                <td className="px-4 py-2.5"><NotifyBadge b={b} /></td>
                <td className="px-4 py-2.5"><Status area="breach" value={b.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
