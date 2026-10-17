import { Link, useParams } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { type Breach, NOTIFY, useBreach, useRaiseBreachRisk, useUpdateBreach } from "../../api/privacy2"
import { useMe } from "../../auth/session"
import { Button } from "../../components/Button"
import { formatDate } from "../../lib/format"
import { BREACH_STATUS, NotifyBadge, SEVERITY, SeverityBadge } from "./Breaches"
import { Status } from "../../components/Status"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"

function Notification({ b, who, canEdit }: { b: Breach; who: "regulator" | "people"; canEdit: boolean }) {
  const update = useUpdateBreach(b.id)
  const choice = who === "regulator" ? b.regulator_notify : b.people_notify
  const notifiedAt = who === "regulator" ? b.regulator_notified_at : b.people_notified_at
  const label = who === "regulator" ? "the authority" : "the people affected"
  return (
    <div className="grid gap-2 rounded-xl border border-line p-4">
      <h3 className="text-[14px] font-semibold capitalize">{label}</h3>
      <label className={LABEL}>
        Notification
        <select
          value={choice}
          disabled={!canEdit}
          onChange={(e) => update.mutate(who === "regulator" ? { regulator_notify: e.target.value as Breach["regulator_notify"] } : { people_notify: e.target.value as Breach["people_notify"] })}
          className={FIELD}
        >
          {Object.entries(NOTIFY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      {notifiedAt ? (
        <p className="text-[13px] font-medium text-ok">Notified {formatDate(notifiedAt)}</p>
      ) : (
        choice === "required" &&
        canEdit && (
          <Button
            size="sm"
            variant="secondary"
            aria-label={`Mark ${label} as notified now`}
            onClick={() => update.mutate(who === "regulator" ? { regulator_notified_at: new Date().toISOString() } : { people_notified_at: new Date().toISOString() })}
          >
            Notified now
          </Button>
        )
      )}
    </div>
  )
}

export function BreachDetailPage() {
  const { id } = useParams({ from: "/app/privacy/breaches/$id" })
  const me = useMe()
  const breach = useBreach(id)
  const update = useUpdateBreach(id)
  const raise = useRaiseBreachRisk(id)
  const [text, setText] = useState({ description: "", containment: "", lessons: "" })
  useEffect(() => {
    if (breach.data) setText({ description: breach.data.description ?? "", containment: breach.data.containment ?? "", lessons: breach.data.lessons ?? "" })
  }, [breach.data])
  if (breach.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (breach.isError) return <p role="alert">{breach.error.message}</p>
  const b = breach.data
  const canEdit = (me.data?.permissions ?? []).includes("privacy:manage")
  const error = update.error ?? raise.error

  return (
    <div className="mx-auto grid max-w-4xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/privacy" search={{ tab: "breaches" }} className="hover:text-fg">Breaches</Link> <span aria-hidden="true">›</span> {b.code}
      </nav>
      <header className="rise relative grid gap-2 overflow-hidden rounded-2xl border border-bad/30 bg-surface p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-bad" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{b.code} · {b.title}</h1>
          <span className="flex flex-wrap gap-1.5">
            <SeverityBadge b={b} />
            <Status area="breach" value={b.status} />
            <NotifyBadge b={b} />
          </span>
        </div>
        <p className="text-[13px] text-fg-2">
          Discovered {formatDate(b.discovered_at)} · notify by {formatDate(b.notify_deadline)}
          {b.hours_left !== null && !b.notification_overdue && ` · ${b.hours_left} hours left`}
          {b.people_affected !== null && ` · about ${b.people_affected} people affected`}
        </p>
      </header>
      <section className="grid gap-3 md:grid-cols-2" aria-label="Notifications">
        <Notification b={b} who="regulator" canEdit={canEdit} />
        <Notification b={b} who="people" canEdit={canEdit} />
      </section>
      <section className={`${CARD} grid gap-3`} aria-label="Assessment">
        <div className="grid gap-3 md:grid-cols-2">
          <label className={LABEL}>
            Severity
            <select value={b.severity} disabled={!canEdit} onChange={(e) => update.mutate({ severity: e.target.value as Breach["severity"] })} className={FIELD}>
              {Object.entries(SEVERITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className={LABEL}>
            Status
            <select value={b.status} disabled={!canEdit} onChange={(e) => update.mutate({ status: e.target.value as Breach["status"] })} className={FIELD}>
              {Object.entries(BREACH_STATUS).map(([k, [v]]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
        {(
          [
            ["description", "What happened and how it was found"],
            ["containment", "Containment and recovery"],
            ["lessons", "Lessons learnt"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className={LABEL}>
            {label}
            <textarea
              rows={3}
              disabled={!canEdit}
              value={text[key]}
              onChange={(e) => setText({ ...text, [key]: e.target.value })}
              onBlur={() => text[key] !== (b[key] ?? "") && update.mutate({ [key]: text[key] || null })}
              className={FIELD}
            />
          </label>
        ))}
        <div className="flex items-center gap-3">
          {b.risk ? (
            <span className="text-[13px] font-semibold text-primary">In the risk register: {b.risk.code}</span>
          ) : (
            canEdit && <Button size="sm" variant="secondary" onClick={() => raise.mutate(undefined)}>Add to the risk register</Button>
          )}
        </div>
      </section>
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
    </div>
  )
}
