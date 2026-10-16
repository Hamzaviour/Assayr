import { Link, useNavigate } from "@tanstack/react-router"
import { type CSSProperties, type FormEvent, useState } from "react"
import {
  type Audit,
  type AuditCounts,
  AUDIT_STATUS_LABEL,
  type AuditFramework,
  FRAMEWORK_LABEL,
  useAudits,
  useCreateAudit,
  useImportAudit,
} from "../api/audits"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"

const order = (i: number) => ({ "--i": i }) as CSSProperties
const FIELD = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"

const RESULT_SEGMENTS: [keyof AuditCounts, string, string][] = [
  ["pass", "pass", "var(--ok)"],
  ["partial", "partial", "var(--warn)"],
  ["fail", "fail", "var(--bad)"],
  ["na", "NA", "var(--idle)"],
]

/** A compact Pass / Partial / Fail / NA bar; untested controls show as the empty track. */
export function ResultBar({ counts }: { counts: AuditCounts }) {
  const untested = counts.total - counts.tested
  const label = [...RESULT_SEGMENTS.map(([key, name]) => `${counts[key]} ${name}`), `${untested} untested`].join(", ")
  return (
    <div role="img" aria-label={label} className="flex h-2.5 w-full overflow-hidden rounded-full bg-subtle">
      <div className="grow-x flex h-full w-full">
        {counts.total > 0 &&
          RESULT_SEGMENTS.filter(([key]) => counts[key] > 0).map(([key, name, color]) => (
            <div key={key} title={`${counts[key]} ${name}`} style={{ width: `${(counts[key] / counts.total) * 100}%`, background: color }} />
          ))}
      </div>
    </div>
  )
}

export function AuditStatus({ status }: { status: Audit["status"] }) {
  const tone =
    status === "completed"
      ? "bg-ok-soft text-ok border-ok/25"
      : status === "in_progress"
        ? "bg-primary-soft text-primary border-primary/25"
        : "bg-transparent text-fg-2 border-line-2 border-dashed"
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${tone}`}>
      {AUDIT_STATUS_LABEL[status]}
    </span>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div role="dialog" aria-label={title} className="rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <h2 className="mb-3 text-[15px] font-semibold">{title}</h2>
      {children}
    </div>
  )
}

function FrameworkSelect({ value, onChange }: { value: AuditFramework; onChange: (v: AuditFramework) => void }) {
  return (
    <label className="grid gap-1 text-[12.5px] text-fg-2">
      Framework
      <select value={value} onChange={(e) => onChange(e.target.value as AuditFramework)} className={FIELD}>
        <option value="nia-2.1">NIA v2.1</option>
        <option value="iso27001">ISO/IEC 27001</option>
      </select>
    </label>
  )
}

function NewAudit({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateAudit()
  const [framework, setFramework] = useState<AuditFramework>("nia-2.1")
  const [title, setTitle] = useState("")

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      { framework, title: title.trim() },
      { onSuccess: (a) => navigate({ to: "/audits/$id", params: { id: a.id } }) },
    )
  }

  return (
    <Panel title="New audit">
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-[200px_minmax(0,1fr)] md:items-end">
        <FrameworkSelect value={framework} onChange={setFramework} />
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Title
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="NIA internal audit 2026"
            required
            maxLength={200}
            className={FIELD}
          />
        </label>
        <div className="flex items-center gap-2 md:col-span-2">
          <Button type="submit" size="sm" disabled={create.isPending || !title.trim()}>
            {create.isPending ? "Creating…" : "Create audit"}
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
        </div>
      </form>
    </Panel>
  )
}

function ImportWorkbook({ onClose }: { onClose: () => void }) {
  const importAudit = useImportAudit()
  const [framework, setFramework] = useState<AuditFramework>("nia-2.1")
  const result = importAudit.data
  return (
    <Panel title="Import workbook">
      <div className="grid gap-3 md:grid-cols-[200px_minmax(0,1fr)] md:items-end">
        <FrameworkSelect value={framework} onChange={setFramework} />
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Workbook (.xlsx)
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={importAudit.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) importAudit.mutate({ framework, file })
              e.target.value = ""
            }}
            className="text-[13px] text-fg"
          />
        </label>
      </div>
      <p className="mt-2 text-[12.5px] text-fg-3">
        One row per control, with the columns of the internal audit report (Sr. No., Domain Name, NIA Control … Control status).
      </p>
      {importAudit.isPending && <p role="status" className="mt-2 text-[13px] text-fg-3">Reading the workbook…</p>}
      {result && (
        <p role="status" className="mt-2 text-[13px] font-medium text-ok">
          Imported {result.imported} controls · {result.unknown_refs.length} not found
          {result.unknown_refs.length > 0 && ` (${result.unknown_refs.slice(0, 10).join(", ")})`}{" "}
          <Link to="/audits/$id" params={{ id: result.audit.id }} className="text-primary hover:underline">Open the audit</Link>
        </p>
      )}
      {importAudit.isError && <p role="alert" className="mt-2 text-[13px] text-bad">{importAudit.error.message}</p>}
      <div className="mt-3">
        <Button type="button" variant="secondary" size="sm" onClick={onClose}>Close</Button>
      </div>
    </Panel>
  )
}

export function AuditsPage() {
  const me = useMe()
  const audits = useAudits()
  const [panel, setPanel] = useState<"new" | "import" | null>(null)
  const canWrite = (me.data?.permissions ?? []).includes("audits:write")
  const list = audits.data ?? []

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="rise flex flex-wrap items-end justify-between gap-3" style={order(0)}>
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Assure</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Internal audits</h1>
          <p className="mt-1 text-[13px] text-fg-2">ISO/IEC 27001 clause 9.2 and NIA internal audits, exported in your report layout.</p>
        </div>
        {canWrite && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setPanel("import")}>Import workbook</Button>
            <Button onClick={() => setPanel("new")}>New audit</Button>
          </div>
        )}
      </header>
      {panel === "new" && <NewAudit onClose={() => setPanel(null)} />}
      {panel === "import" && <ImportWorkbook onClose={() => setPanel(null)} />}
      {audits.isError && <p role="alert">{audits.error.message}</p>}
      {audits.isPending && <div className="h-40 animate-pulse rounded-xl bg-subtle" aria-label="Loading" />}
      {audits.isSuccess && list.length === 0 && (
        <p className="rounded-xl border border-dashed border-line-2 p-8 text-center text-fg-3">
          No audits yet.{canWrite && " Create one, or import an existing internal audit workbook."}
        </p>
      )}
      <ul className="grid gap-3">
        {list.map((a, i) => (
          <li key={a.id} className="lift rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5" style={order(i + 1)}>
            <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-brand via-brand-bright to-brand-deep" />
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="mb-1 text-[12px] font-semibold text-primary">{FRAMEWORK_LABEL[a.framework]}</p>
                <Link to="/audits/$id" params={{ id: a.id }} className="text-[16px] font-semibold hover:text-primary">
                  {a.title}
                </Link>
                <p className="mt-1 text-[12.5px] text-fg-3">
                  {a.auditor ? `Auditor: ${a.auditor.full_name}` : "No auditor"}
                  {a.period_start && ` · ${formatDate(a.period_start)}`}
                  {a.period_end && ` – ${formatDate(a.period_end)}`}
                </p>
              </div>
              <AuditStatus status={a.status} />
            </div>
            <div className="mt-4 grid gap-1.5">
              <ResultBar counts={a.counts} />
              <p className="text-[12.5px] tabular-nums text-fg-2">
                {a.counts.tested} of {a.counts.total} tested · {a.counts.pass} pass · {a.counts.partial} partial · {a.counts.fail} fail
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
