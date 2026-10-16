import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import {
  type AuditDetail,
  type AuditItem,
  type AuditChanges,
  type AuditResult,
  auditExportUrl,
  FRAMEWORK_LABEL,
  RESULT_LABEL,
  type TestType,
  useAddAuditItems,
  useAudit,
  useCompleteAudit,
  useReopenAudit,
  useRemoveAuditItem,
  useUpdateAudit,
  useUpdateAuditItem,
} from "../api/audits"
import { usePeople } from "../api/people"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"
import { AuditStatus, ResultBar } from "./Audits"

const CARD = "rounded-xl border border-line bg-surface p-5"
const FIELD = "rounded-lg border border-line-2 bg-surface px-2 py-1 text-[13px] text-fg"
const RESULT_TONE: Record<AuditResult, string> = {
  pass: "text-ok",
  partial: "text-warn",
  fail: "text-bad",
  na: "text-fg-3",
}

type Filter = "all" | "untested" | "issues"
const FILTERS: [Filter, string][] = [
  ["all", "All"],
  ["untested", "Untested"],
  ["issues", "Fail & partial"],
]

export function AuditDetailPage() {
  const { id } = useParams({ from: "/app/audits/$id" })
  const audit = useAudit(id)
  const [filter, setFilter] = useState<Filter>("all")
  if (audit.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (audit.isError) return <p role="alert">{audit.error.message}</p>
  const a = audit.data
  const editable = a.can_write && a.status !== "completed"
  const shown = a.items.filter((i) =>
    filter === "untested" ? !i.result : filter === "issues" ? i.result === "fail" || i.result === "partial" : true,
  )
  const groups = new Map<string, AuditItem[]>()
  for (const item of shown) groups.set(item.domain, [...(groups.get(item.domain) ?? []), item])

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/audits" className="hover:text-fg">Internal audits</Link> <span aria-hidden="true">›</span> {a.title}
      </nav>
      <Header audit={a} />
      {editable && <AddControls audit={a} />}
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-3 py-1 text-[12.5px] font-semibold transition-colors duration-200 ${
              filter === key ? "border-primary bg-primary text-on-primary" : "border-line text-fg-2 hover:bg-subtle"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {a.items.length === 0 && (
        <p className="rounded-xl border border-dashed border-line-2 p-8 text-center text-fg-3">
          No controls in this audit yet.{editable && " Add all controls, a domain, or specific references above."}
        </p>
      )}
      {[...groups].map(([domain, items]) => (
        <section key={domain} className="rounded-xl border border-line bg-surface" aria-labelledby={`d-${domain}`}>
          <h2 id={`d-${domain}`} className="border-b border-line px-4 py-3 text-[14.5px] font-semibold">
            {domain}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-fg-3">
                  <th className="px-4 py-2 font-medium">Control</th>
                  <th className="px-4 py-2 font-medium">Assessment area</th>
                  <th className="px-4 py-2 font-medium">Test</th>
                  <th className="px-4 py-2 font-medium">M/A</th>
                  <th className="px-4 py-2 font-medium">Result</th>
                  <th className="px-4 py-2 font-medium">Notes</th>
                  {editable && <th className="px-2 py-2" aria-label="Remove" />}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <ItemRow key={item.id} audit={a} item={item} editable={editable} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

function Header({ audit: a }: { audit: AuditDetail }) {
  const complete = useCompleteAudit(a.id)
  const reopen = useReopenAudit(a.id)
  const [reopening, setReopening] = useState(false)
  const [reason, setReason] = useState("")
  const untested = a.items.filter((i) => !i.result).length
  const tested = a.items.length - untested

  return (
    <header className="rise relative grid gap-4 overflow-hidden rounded-2xl border border-line bg-surface p-6">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-1 text-[12.5px] font-semibold text-primary">{FRAMEWORK_LABEL[a.framework]} · internal audit</p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{a.title}</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            {a.auditor ? `Auditor: ${a.auditor.full_name}` : "No auditor"}
            {a.completed_at && a.completed_by && ` · Completed ${formatDate(a.completed_at)} by ${a.completed_by.full_name}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AuditStatus status={a.status} />
          <a
            href={auditExportUrl(a.id)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[13px] font-semibold text-primary hover:bg-subtle"
          >
            Export Excel
          </a>
          {a.can_write && a.status !== "completed" && (
            <Button size="sm" disabled={untested > 0 || a.items.length === 0 || complete.isPending} onClick={() => complete.mutate()}>
              Complete audit
            </Button>
          )}
          {a.can_reopen && !reopening && (
            <Button size="sm" variant="secondary" onClick={() => setReopening(true)}>
              Reopen
            </Button>
          )}
        </div>
      </div>
      <div className="grid gap-1.5">
        <ResultBar counts={a.counts} />
        <p className="text-[12.5px] tabular-nums text-fg-2">
          <span>{tested} of {a.items.length} tested</span> · {a.counts.pass} pass · {a.counts.partial} partial · {a.counts.fail} fail ·{" "}
          {a.counts.na} NA
        </p>
        {a.can_write && a.status !== "completed" && untested > 0 && (
          <p className="text-[12.5px] text-fg-3">
            {untested} {untested === 1 ? "control still needs a result." : "controls still need a result."}
          </p>
        )}
      </div>
      {(a.scope_note || a.conclusion) && (
        <dl className="grid gap-2 text-[13px] md:grid-cols-2">
          {a.scope_note && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Scope</dt>
              <dd className="whitespace-pre-line text-fg-2">{a.scope_note}</dd>
            </div>
          )}
          {a.conclusion && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Conclusion</dt>
              <dd className="whitespace-pre-line text-fg-2">{a.conclusion}</dd>
            </div>
          )}
        </dl>
      )}
      {a.can_write && a.status !== "completed" && <DetailsEditor audit={a} />}
      {reopening && (
        <div className="grid gap-2 rounded-lg bg-subtle p-3">
          <label className="grid gap-1 text-[12.5px] text-fg-2">
            Why reopen?
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} className={FIELD} />
          </label>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={!reason.trim() || reopen.isPending}
              onClick={() => reopen.mutate(reason.trim(), { onSuccess: () => setReopening(false) })}
            >
              Confirm reopen
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setReopening(false)}>Cancel</Button>
          </div>
        </div>
      )}
      {(complete.isError || reopen.isError) && (
        <p role="alert" className="text-[13px] text-bad">{(complete.error ?? reopen.error)?.message}</p>
      )}
    </header>
  )
}

function AddControls({ audit: a }: { audit: AuditDetail }) {
  const add = useAddAuditItems(a.id)
  const [domain, setDomain] = useState("")
  const [refs, setRefs] = useState("")
  const nia = a.framework === "nia-2.1"

  function onDomain(event: FormEvent) {
    event.preventDefault()
    add.mutate({ domain: domain.trim() }, { onSuccess: () => setDomain("") })
  }
  function onRefs(event: FormEvent) {
    event.preventDefault()
    const list = refs.split(/[,;\n]/).map((r) => r.trim()).filter(Boolean)
    add.mutate({ refs: list }, { onSuccess: () => setRefs("") })
  }

  return (
    <section aria-label="Add controls" className={`${CARD} grid gap-3`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold">Add controls</h2>
        <Button size="sm" variant="secondary" disabled={add.isPending} onClick={() => add.mutate({ all: true })}>
          Add all controls
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <form onSubmit={onDomain} className="flex items-end gap-2">
          <label className="grid flex-1 gap-1 text-[12.5px] text-fg-2">
            Domain
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder={nia ? "Domain code, e.g. PS" : "Theme, e.g. People"}
              className={FIELD}
            />
          </label>
          <Button type="submit" size="sm" variant="secondary" disabled={!domain.trim() || add.isPending}>Add domain</Button>
        </form>
        <form onSubmit={onRefs} className="flex items-end gap-2">
          <label className="grid flex-1 gap-1 text-[12.5px] text-fg-2">
            References
            <input
              value={refs}
              onChange={(e) => setRefs(e.target.value)}
              placeholder={nia ? "SU 5, SU 7" : "A.5.1, A.8.13"}
              className={FIELD}
            />
          </label>
          <Button type="submit" size="sm" variant="secondary" disabled={!refs.trim() || add.isPending}>Add references</Button>
        </form>
      </div>
      {add.isError && <p role="alert" className="text-[13px] text-bad">{add.error.message}</p>}
    </section>
  )
}

function ItemRow({ audit: a, item, editable }: { audit: AuditDetail; item: AuditItem; editable: boolean }) {
  const update = useUpdateAuditItem(a.id)
  const remove = useRemoveAuditItem(a.id)
  const [area, setArea] = useState(item.assessment_area ?? "")
  const [notes, setNotes] = useState(item.notes ?? "")
  useEffect(() => setArea(item.assessment_area ?? ""), [item.assessment_area])
  useEffect(() => setNotes(item.notes ?? ""), [item.notes])
  const save = (changes: Parameters<typeof update.mutate>[0]["changes"]) =>
    update.mutate(
      { itemId: item.id, changes },
      {
        onError: () => {
          setArea(item.assessment_area ?? "")
          setNotes(item.notes ?? "")
        },
      },
    )
  const link =
    a.framework === "nia-2.1" ? (
      <Link to="/nia/$ref" params={{ ref: item.ref }} className="font-mono text-[12.5px] font-medium text-fg hover:text-primary">
        {item.ref}
      </Link>
    ) : (
      <Link to="/controls/$code" params={{ code: item.ref }} className="font-mono text-[12.5px] font-medium text-fg hover:text-primary">
        {item.ref}
      </Link>
    )

  if (!editable) {
    return (
      <tr className="border-t border-line align-top">
        <td className="whitespace-nowrap px-4 py-2.5">{link}</td>
        <td className="min-w-64 px-4 py-2.5 text-fg-2">{item.assessment_area || "—"}</td>
        <td className="px-4 py-2.5">{item.test_type ?? "—"}</td>
        <td className="px-4 py-2.5">{item.requirement ?? "—"}</td>
        <td className={`px-4 py-2.5 font-semibold ${item.result ? RESULT_TONE[item.result] : "text-fg-3"}`}>
          {item.result ? RESULT_LABEL[item.result] : "Not tested"}
        </td>
        <td className="min-w-48 px-4 py-2.5 text-fg-2">{item.notes || "—"}</td>
      </tr>
    )
  }

  return (
    <tr className="border-t border-line align-top">
      <td className="whitespace-nowrap px-4 py-2.5">{link}</td>
      <td className="min-w-64 px-4 py-2">
        <textarea
          aria-label={`Assessment area for ${item.ref}`}
          value={area}
          rows={2}
          maxLength={5000}
          onChange={(e) => setArea(e.target.value)}
          onBlur={() => area.trim() !== (item.assessment_area ?? "") && save({ assessment_area: area.trim() || null })}
          className={`${FIELD} w-full`}
        />
      </td>
      <td className="px-4 py-2">
        <select
          aria-label={`Test type for ${item.ref}`}
          value={item.test_type ?? ""}
          onChange={(e) => save({ test_type: (e.target.value || null) as TestType | null })}
          className={FIELD}
        >
          <option value="">—</option>
          <option value="DA">DA</option>
          <option value="OEA">OEA</option>
          <option value="Both">Both</option>
        </select>
      </td>
      <td className="px-4 py-2">
        <select
          aria-label={`Mandatory or additional for ${item.ref}`}
          value={item.requirement ?? ""}
          onChange={(e) => save({ requirement: (e.target.value || null) as "M" | "A" | null })}
          className={FIELD}
        >
          <option value="">—</option>
          <option value="M">M</option>
          <option value="A">A</option>
        </select>
      </td>
      <td className="px-4 py-2">
        <select
          aria-label={`Result for ${item.ref}`}
          value={item.result ?? ""}
          onChange={(e) => save({ result: (e.target.value || null) as AuditResult | null })}
          className={`${FIELD} font-semibold ${item.result ? RESULT_TONE[item.result] : ""}`}
        >
          <option value="">Not tested</option>
          <option value="pass">Pass</option>
          <option value="partial">Partial</option>
          <option value="fail">Fail</option>
          <option value="na">NA</option>
        </select>
      </td>
      <td className="min-w-48 px-4 py-2">
        <input
          aria-label={`Notes for ${item.ref}`}
          value={notes}
          maxLength={5000}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => notes.trim() !== (item.notes ?? "") && save({ notes: notes.trim() || null })}
          className={`${FIELD} w-full`}
        />
        {update.isError && <p role="alert" className="mt-1 text-[12px] font-medium text-bad">{update.error.message}</p>}
      </td>
      <td className="px-2 py-2">
        <button
          type="button"
          aria-label={`Remove ${item.ref}`}
          disabled={remove.isPending}
          onClick={() => remove.mutate(item.id)}
          className="rounded px-1.5 text-fg-3 hover:bg-subtle hover:text-bad"
        >
          ×
        </button>
      </td>
    </tr>
  )
}

function DetailsEditor({ audit: a }: { audit: AuditDetail }) {
  const [open, setOpen] = useState(false)
  const update = useUpdateAudit(a.id)
  const people = usePeople()
  const [title, setTitle] = useState(a.title)
  const [start, setStart] = useState(a.period_start ?? "")
  const [end, setEnd] = useState(a.period_end ?? "")
  const [auditorId, setAuditorId] = useState(a.auditor?.id ?? "")
  const [scope, setScope] = useState(a.scope_note ?? "")
  const [conclusion, setConclusion] = useState(a.conclusion ?? "")

  if (!open) {
    return (
      <div>
        <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>Edit details</Button>
      </div>
    )
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: AuditChanges = {}
    if (title.trim() && title.trim() !== a.title) changes.title = title.trim()
    if (start !== (a.period_start ?? "")) changes.period_start = start || null
    if (end !== (a.period_end ?? "")) changes.period_end = end || null
    if (auditorId !== (a.auditor?.id ?? "")) changes.auditor_id = auditorId || null
    if (scope.trim() !== (a.scope_note ?? "")) changes.scope_note = scope.trim() || null
    if (conclusion.trim() !== (a.conclusion ?? "")) changes.conclusion = conclusion.trim() || null
    update.mutate(changes, { onSuccess: () => setOpen(false) })
  }

  const label = "grid gap-1 text-[12.5px] text-fg-2"
  return (
    <form onSubmit={onSubmit} className="grid gap-3 rounded-lg bg-subtle p-4 md:grid-cols-2">
      <label className={`${label} md:col-span-2`}>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} className={FIELD} />
      </label>
      <label className={label}>
        Period start
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={FIELD} />
      </label>
      <label className={label}>
        Period end
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={FIELD} />
      </label>
      <label className={`${label} md:col-span-2`}>
        Auditor
        <select value={auditorId} onChange={(e) => setAuditorId(e.target.value)} className={FIELD}>
          <option value="">No auditor</option>
          {a.auditor && !(people.data ?? []).some((p) => p.id === a.auditor?.id) && (
            <option value={a.auditor.id}>{a.auditor.full_name}</option>
          )}
          {(people.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>{p.full_name}</option>
          ))}
        </select>
      </label>
      <label className={label}>
        Scope note
        <textarea value={scope} onChange={(e) => setScope(e.target.value)} rows={3} maxLength={5000} className={FIELD} />
      </label>
      <label className={label}>
        Conclusion
        <textarea value={conclusion} onChange={(e) => setConclusion(e.target.value)} rows={3} maxLength={10000} className={FIELD} />
      </label>
      <div className="flex items-center gap-2 md:col-span-2">
        <Button type="submit" size="sm" disabled={update.isPending}>Save details</Button>
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
        {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      </div>
    </form>
  )
}
