import { Link } from "@tanstack/react-router"
import { type FormEvent, Fragment, useState } from "react"
import { IMPLEMENTATION_LABEL } from "../api/controls"
import { SOURCE_LABEL, useDecideSoa, useSoa, useSoaVersions, useSubmitSoa, useUpdateSoaItems } from "../api/soa"
import type { SoaChecks, SoaItem, SoaVersion } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { Icon } from "../components/icons"
import { formatDate } from "../lib/format"

const VERSION_STATUS: Record<string, string> = { pending: "Waiting for approval", approved: "Approved", returned: "Returned" }
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const linkClass = "rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3"
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`

export function SoaPage() {
  const me = useMe()
  const perms = me.data?.permissions ?? []
  const canEdit = perms.includes("soa:write")
  const canApprove = perms.includes("soa:approve")
  const soa = useSoa()
  const versions = useSoaVersions()
  const submit = useSubmitSoa()
  const update = useUpdateSoaItems()
  const [selected, setSelected] = useState<string[]>([])
  const [excluding, setExcluding] = useState<string | null>(null)

  if (soa.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (soa.isError) return <p role="alert">{soa.error.message}</p>
  const { items, checks } = soa.data
  const pending = versions.data?.find((v) => v.status === "pending")
  const approved = versions.data?.find((v) => v.status === "approved")
  const toggle = (code: string) =>
    setSelected((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]))

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Comply</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Statement of Applicability</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            {approved && approved.decided_at
              ? `Approved v${approved.version_no} · ${formatDate(approved.decided_at)}`
              : "No approved version yet"}
            {pending ? ` · ` : ""}
            {pending && <span>{`v${pending.version_no} is waiting for approval`}</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a href="/api/v1/soa/export.xlsx" className={linkClass}>Export XLSX</a>
          {canEdit && (
            <Button onClick={() => submit.mutate()} disabled={!checks.ok || Boolean(pending) || submit.isPending}>
              Submit for approval
            </Button>
          )}
        </div>
      </header>
      {submit.isError && <p role="alert" className="text-[13px] text-bad">{submit.error.message}</p>}
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      <Checks checks={checks} />
      {canEdit && selected.length > 0 && <BulkSources codes={selected} onDone={() => setSelected([])} />}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {canEdit && <th className="px-3.5 py-3"><span className="sr-only">Select</span></th>}
              {["ID", "Control", "Applicable", "Justification", "Implementation", "Evidence"].map((h) => (
                <th key={h} className="px-3.5 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <Fragment key={row.code}>
                <tr className="border-t border-line align-top hover:bg-subtle">
                  {canEdit && (
                    <td className="px-3.5 py-2.5">
                      <input type="checkbox" aria-label={`Select ${row.code}`} checked={selected.includes(row.code)}
                        onChange={() => toggle(row.code)} />
                    </td>
                  )}
                  <td className="px-3.5 py-2.5"><ControlId code={row.code} /></td>
                  <td className="min-w-56 px-3.5 py-2.5">
                    <Link to="/controls/$code" params={{ code: row.code }} className="hover:text-primary">{row.title}</Link>
                  </td>
                  <td className="whitespace-nowrap px-3.5 py-2.5">
                    <Applicability row={row} canEdit={canEdit} onExclude={() => setExcluding(row.code)}
                      onInclude={() => update.mutate({ codes: [row.code], applicable: true })} />
                  </td>
                  <td className="px-3.5 py-2.5"><Justification row={row} /></td>
                  <td className="px-3.5 py-2.5 text-fg-2">
                    {row.applicable ? IMPLEMENTATION_LABEL[row.implementation_status] ?? row.implementation_status : "—"}
                  </td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">
                    {row.applicable ? `${row.evidence_verified} of ${row.evidence_required}` : "—"}
                  </td>
                </tr>
                {excluding === row.code && (
                  <tr>
                    <td colSpan={canEdit ? 7 : 6} className="bg-subtle px-3.5 py-3">
                      <ExcludeForm code={row.code} onDone={() => setExcluding(null)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>
      <Versions versions={versions.data ?? []} canApprove={canApprove} />
    </div>
  )
}

function Checks({ checks }: { checks: SoaChecks }) {
  const lines = [
    { ok: checks.orphans.length === 0, text: `${plural(checks.orphans.length, "applicable control")} without a justification` },
    {
      ok: checks.excluded_mitigating.length === 0,
      text: `${plural(checks.excluded_mitigating.length, "excluded control")} that mitigate a risk`,
    },
    {
      ok: checks.untreated_risks.length === 0,
      text: `${plural(checks.untreated_risks.length, "risk")} above appetite without a treatment`,
    },
  ]
  return (
    <section aria-label="Traceability checks"
      className={`grid gap-2 rounded-xl border px-5 py-3 text-[13px] ${checks.ok ? "border-ok/30 bg-ok-soft" : "border-warn/30 bg-warn-soft"}`}>
      <ul className="flex flex-wrap gap-x-6 gap-y-1">
        {lines.map((line) => (
          <li key={line.text} className={`flex items-center gap-1.5 ${line.ok ? "text-ok" : "text-warn"}`}>
            <Icon name={line.ok ? "pass" : "warn"} size={14} />
            <span className="text-fg">{line.text}</span>
          </li>
        ))}
      </ul>
      {checks.excluded_mitigating.map((e) => (
        <p key={e.code}>{`${e.code} is excluded but mitigates ${e.risks.join(", ")}.`}</p>
      ))}
      {checks.untreated_risks.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5">
          Choose a treatment for:
          {checks.untreated_risks.map((code) => (
            <Link key={code} to="/risks/$code" params={{ code }} className="font-mono text-primary underline">{code}</Link>
          ))}
        </p>
      )}
    </section>
  )
}

function Applicability({ row, canEdit, onExclude, onInclude }: {
  row: SoaItem
  canEdit: boolean
  onExclude: () => void
  onInclude: () => void
}) {
  if (!canEdit) return <span>{row.applicable ? "Yes" : "No"}</span>
  return row.applicable ? (
    <Button variant="ghost" size="sm" aria-label={`Exclude ${row.code}`} onClick={onExclude}>● Yes</Button>
  ) : (
    <Button variant="ghost" size="sm" aria-label={`Include ${row.code}`} onClick={onInclude}>○ No</Button>
  )
}

function Justification({ row }: { row: SoaItem }) {
  if (!row.applicable) return <span className="text-fg-2">{`“${row.exclusion_reason ?? ""}”`}</span>
  if (row.sources.length === 0) return <span className="text-warn">No justification</span>
  return (
    <span className="flex flex-wrap gap-1">
      {row.sources.map((s) =>
        s.kind === "risk" && s.ref ? (
          <Link key={s.label} to="/risks/$code" params={{ code: s.ref }} className="rounded-md bg-primary-soft px-1.5 py-0.5 text-[12px] text-primary">
            {s.label}
          </Link>
        ) : (
          <span key={s.label} className="rounded-md bg-subtle px-1.5 py-0.5 text-[12px]">{s.label}</span>
        ),
      )}
    </span>
  )
}

function ExcludeForm({ code, onDone }: { code: string; onDone: () => void }) {
  const update = useUpdateSoaItems()
  const [reason, setReason] = useState("")
  const id = `exclude-${code.replace(/\./g, "-")}`

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({ codes: [code], applicable: false, exclusion_reason: reason.trim() })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid max-w-xl gap-2">
      <label htmlFor={id} className="text-[13px] font-medium">{`Reason for excluding ${code}`}</label>
      <textarea id={id} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!reason.trim() || update.isPending}>Exclude</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}

function BulkSources({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const update = useUpdateSoaItems()
  const [kinds, setKinds] = useState<string[]>([])

  async function apply() {
    await update.mutateAsync({ codes, sources: kinds })
    onDone()
  }

  return (
    <section aria-label="Bulk edit" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-5 py-3 text-[13px]">
      <span className="font-medium">{codes.length} selected · justification sources:</span>
      {Object.entries(SOURCE_LABEL).map(([kind, label]) => (
        <label key={kind} className="flex items-center gap-1.5">
          <input type="checkbox" checked={kinds.includes(kind)}
            onChange={() => setKinds((k) => (k.includes(kind) ? k.filter((x) => x !== kind) : [...k, kind]))} />
          {label}
        </label>
      ))}
      <Button size="sm" onClick={() => void apply()} disabled={update.isPending}>
        {`Apply to ${plural(codes.length, "control")}`}
      </Button>
    </section>
  )
}

function Versions({ versions, canApprove }: { versions: SoaVersion[]; canApprove: boolean }) {
  const decide = useDecideSoa()
  const [returning, setReturning] = useState<number | null>(null)
  const [reason, setReason] = useState("")

  return (
    <section aria-labelledby="versions-heading" className="rounded-xl border border-line bg-surface">
      <h2 id="versions-heading" className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Versions</h2>
      {decide.isError && <p role="alert" className="px-5 py-2 text-[13px] text-bad">{decide.error.message}</p>}
      {versions.length === 0 ? (
        <p className="px-5 py-4 text-[13px] text-fg-3">No version has been submitted yet.</p>
      ) : (
        <ul>
          {versions.map((v) => (
            <li key={v.version_no} className="grid gap-2 border-b border-line px-5 py-3 text-[13px] last:border-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <b>{`v${v.version_no}`}</b> · {VERSION_STATUS[v.status] ?? v.status} · prepared by {v.prepared_by ?? "unknown"}{" "}
                  on {formatDate(v.prepared_at)}
                  {v.decided_by && v.decided_at ? ` · ${v.status} by ${v.decided_by} on ${formatDate(v.decided_at)}` : ""}
                  {` · ${v.applicable} applicable, ${v.excluded} excluded`}
                </span>
                <span className="flex items-center gap-2">
                  <a href={`/api/v1/soa/versions/${v.version_no}/export.xlsx`} className={linkClass}>Export</a>
                  {canApprove && v.status === "pending" && (
                    <>
                      <Button size="sm" aria-label={`Approve v${v.version_no}`} disabled={decide.isPending}
                        onClick={() => decide.mutate({ version: v.version_no, decision: "approve" })}>
                        Approve
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setReturning(v.version_no)}>Return</Button>
                    </>
                  )}
                </span>
              </div>
              {v.decision_note && <p className="text-fg-2">{`“${v.decision_note}”`}</p>}
              {returning === v.version_no && (
                <form className="grid max-w-xl gap-2" onSubmit={(e) => {
                  e.preventDefault()
                  decide.mutate({ version: v.version_no, decision: "return", reason: reason.trim() }, {
                    onSuccess: () => { setReturning(null); setReason("") },
                  })
                }}>
                  <label htmlFor={`return-${v.version_no}`} className="font-medium">What needs to change?</label>
                  <textarea id={`return-${v.version_no}`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
                  <div><Button type="submit" size="sm" disabled={!reason.trim()}>Return to the preparer</Button></div>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
