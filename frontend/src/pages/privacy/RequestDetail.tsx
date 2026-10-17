import { Link, useParams } from "@tanstack/react-router"
import { useState } from "react"
import { REQUEST_OUTCOME, REQUEST_TYPE, useCloseRequest, useRequest, useUpdateRequest } from "../../api/privacy2"
import { useMe } from "../../auth/session"
import { Button } from "../../components/Button"
import { formatDate } from "../../lib/format"
import { CHANNEL, DueBadge } from "./Requests"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"

export function RequestDetailPage() {
  const { id } = useParams({ from: "/app/privacy/requests/$id" })
  const me = useMe()
  const request = useRequest(id)
  const update = useUpdateRequest(id)
  const close = useCloseRequest(id)
  const [step, setStep] = useState("")
  const [response, setResponse] = useState<string | null>(null)
  const [outcome, setOutcome] = useState("")
  const [reason, setReason] = useState("")
  if (request.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (request.isError) return <p role="alert">{request.error.message}</p>
  const r = request.data
  const open = r.status !== "closed"
  const canEdit = open && (me.data?.permissions ?? []).includes("privacy:manage")
  const error = update.error ?? close.error

  return (
    <div className="mx-auto grid max-w-4xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/privacy" search={{ tab: "requests" }} className="hover:text-fg">Data subject requests</Link> <span aria-hidden="true">›</span> {r.code}
      </nav>
      <header className="rise relative flex flex-wrap items-start justify-between gap-3 overflow-hidden rounded-2xl border border-line bg-surface p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
        <div>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{r.code} · {REQUEST_TYPE[r.type] ?? r.type}</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            {r.requester_name}{r.requester_contact ? ` · ${r.requester_contact}` : ""} · {CHANNEL[r.channel] ?? r.channel} · received {formatDate(r.received_on)} · due {formatDate(r.due_on)}
          </p>
        </div>
        <DueBadge r={r} />
      </header>
      <section className={`${CARD} grid gap-3`} aria-label="Handling">
        <label className="flex items-center gap-2 text-[13.5px]">
          <input type="checkbox" disabled={!canEdit} checked={r.identity_verified} onChange={(e) => update.mutate({ identity_verified: e.target.checked })} />
          Identity verified
        </label>
        <h2 className="text-[14px] font-semibold">Steps</h2>
        {r.steps.length === 0 && <p className="text-[13px] text-fg-3">No steps yet.</p>}
        <ul className="grid gap-1">
          {r.steps.map((s, i) => (
            <li key={`${i}-${s.text}`}>
              <label className="flex items-center gap-2 text-[13.5px]">
                <input
                  type="checkbox"
                  disabled={!canEdit}
                  checked={s.done}
                  onChange={(e) => update.mutate({ steps: r.steps.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)) })}
                />
                <span className={s.done ? "text-fg-3 line-through" : ""}>{s.text}</span>
              </label>
            </li>
          ))}
        </ul>
        {canEdit && (
          <div className="flex items-end gap-2">
            <label className={`${LABEL} flex-1`}>
              New step
              <input value={step} onChange={(e) => setStep(e.target.value)} maxLength={300} className={FIELD} />
            </label>
            <Button
              size="sm"
              variant="secondary"
              disabled={!step.trim()}
              onClick={() => update.mutate({ steps: [...r.steps, { text: step.trim(), done: false }] }, { onSuccess: () => setStep("") })}
            >
              Add step
            </Button>
          </div>
        )}
        <label className={LABEL}>
          Response to the requester
          <textarea
            rows={3}
            disabled={!canEdit}
            value={response ?? r.response ?? ""}
            onChange={(e) => setResponse(e.target.value)}
            onBlur={() => response !== null && response !== (r.response ?? "") && update.mutate({ response: response || null })}
            className={FIELD}
          />
        </label>
      </section>
      {canEdit && (
        <section className={`${CARD} grid gap-3 md:grid-cols-[220px_minmax(0,1fr)_auto] md:items-end`} aria-label="Close the request">
          <label className={LABEL}>
            Outcome
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className={FIELD}>
              <option value="">Choose…</option>
              {Object.entries(REQUEST_OUTCOME).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          {outcome === "refused" ? (
            <label className={LABEL}>
              Reason for refusal
              <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={5000} className={FIELD} />
            </label>
          ) : (
            <span />
          )}
          <Button
            size="sm"
            disabled={!outcome || (outcome === "refused" && !reason.trim()) || close.isPending}
            onClick={() => close.mutate({ outcome, refusal_reason: outcome === "refused" ? reason.trim() : null, response: response ?? r.response })}
          >
            Close request
          </Button>
        </section>
      )}
      {!open && r.refusal_reason && <p className={`${CARD} text-[13px]`}>Refused because: {r.refusal_reason}</p>}
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
    </div>
  )
}
