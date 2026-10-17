import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { REQUEST_OUTCOME, REQUEST_TYPE, type SubjectRequest, useCreateRequest, useRequests } from "../../api/privacy2"
import { Button } from "../../components/Button"
import { formatDate } from "../../lib/format"
import { Tag } from "../Privacy"
import { StatusBar } from "../../components/StatusBar"
import { countBy, statusSegments } from "../../lib/statusBars"

const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
export const CHANNEL: Record<string, string> = { email: "Email", phone: "Phone", letter: "Letter", in_person: "In person", other: "Other" }

/** Due-date badge: red when overdue, amber in the last 5 days, grey otherwise; green once closed. */
export function DueBadge({ r }: { r: Pick<SubjectRequest, "status" | "days_left" | "overdue" | "outcome"> }) {
  if (r.status === "closed") return <Tag tone="bg-ok-soft text-ok border-ok/25">Closed{r.outcome ? ` · ${REQUEST_OUTCOME[r.outcome]}` : ""}</Tag>
  const d = r.days_left ?? 0
  if (r.overdue) return <Tag tone="bg-bad text-white border-bad">{-d} {-d === 1 ? "day" : "days"} overdue</Tag>
  if (d === 0) return <Tag tone="bg-warn text-white border-warn">Due today</Tag>
  return <Tag tone={d <= 5 ? "bg-warn-soft text-warn border-warn/25" : "bg-subtle text-fg-2 border-line"}>{d} {d === 1 ? "day" : "days"} left</Tag>
}

function NewRequest({ onClose }: { onClose: () => void }) {
  const create = useCreateRequest()
  const [form, setForm] = useState({ type: "access", requester_name: "", requester_contact: "", channel: "email", received_on: new Date().toISOString().slice(0, 10) })
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      { ...form, requester_name: form.requester_name.trim(), requester_contact: form.requester_contact.trim() || null },
      { onSuccess: onClose },
    )
  }
  return (
    <div role="dialog" aria-label="Log a data subject request" className="rise m-4 rounded-2xl border border-line bg-surface p-5">
      <h2 className="mb-3 text-[15px] font-semibold">Log a data subject request</h2>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-3">
        <label className={LABEL}>
          Type
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className={FIELD}>
            {Object.entries(REQUEST_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Requester
          <input value={form.requester_name} onChange={(e) => setForm({ ...form, requester_name: e.target.value })} required maxLength={200} className={FIELD} />
        </label>
        <label className={LABEL}>
          Contact
          <input value={form.requester_contact} onChange={(e) => setForm({ ...form, requester_contact: e.target.value })} maxLength={300} className={FIELD} />
        </label>
        <label className={LABEL}>
          Channel
          <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} className={FIELD}>
            {Object.entries(CHANNEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Received on
          <input type="date" value={form.received_on} onChange={(e) => setForm({ ...form, received_on: e.target.value })} required className={FIELD} />
        </label>
        <p className="self-end text-[12px] text-fg-3">Due 30 days after receipt unless you change it later.</p>
        <div className="flex items-center gap-2 md:col-span-3">
          <Button type="submit" size="sm" disabled={!form.requester_name.trim() || !form.received_on || create.isPending}>Log request</Button>
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
          {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
        </div>
      </form>
    </div>
  )
}

export function Requests({ canManage }: { canManage: boolean }) {
  const requests = useRequests()
  const [creating, setCreating] = useState(false)
  const all = requests.data ?? []
  const [status, setStatus] = useState<string | null>(null)
  const rows = status ? all.filter((x) => x.status === status) : all
  return (
    <div>
      {canManage && !creating && (
        <div className="flex justify-end px-4 pt-3">
          <Button size="sm" onClick={() => setCreating(true)}>Log request</Button>
        </div>
      )}
      {creating && <NewRequest onClose={() => setCreating(false)} />}
      {requests.isError && <p role="alert" className="p-4">{requests.error.message}</p>}
      {requests.isSuccess && rows.length === 0 && <p className="p-8 text-center text-fg-3">No requests logged yet.</p>}
      {all.length > 0 && (
        <div className="border-b border-line px-4 py-3">
          <StatusBar label="Requests by status" selected={status} onSelect={setStatus} segments={statusSegments("request", countBy(all, (x) => x.status))} />
        </div>
      )}
      {rows.length > 0 && (
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["Request", "Type", "Requester", "Received", "Due", "Deadline"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={`border-t border-line hover:bg-subtle ${r.overdue ? "bg-bad-soft/40" : ""}`}>
                <td className="px-4 py-2.5">
                  <Link to="/privacy/requests/$id" params={{ id: r.id }} className="font-mono text-[12.5px] font-semibold text-primary hover:underline">
                    {r.code}
                  </Link>
                </td>
                <td className="px-4 py-2.5">{REQUEST_TYPE[r.type] ?? r.type}</td>
                <td className="px-4 py-2.5 text-fg-2">{r.requester_name}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{formatDate(r.received_on)}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{formatDate(r.due_on)}</td>
                <td className="px-4 py-2.5"><DueBadge r={r} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
