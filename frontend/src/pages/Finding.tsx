import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import {
  type CorrectiveAction,
  type FindingChanges,
  type FindingDetail,
  GRADE_LABEL,
  type Grade,
  actionFileUrl,
  isNonconformity,
  useAddAction,
  useCloseFinding,
  useDeleteAction,
  useDeleteActionFile,
  useFinding,
  useRaiseFindingRisk,
  useReopenFinding,
  useUpdateAction,
  useUpdateFinding,
  useUploadActionFile,
  useVerifyFinding,
} from "../api/findings"
import { usePeople } from "../api/people"
import { Button } from "../components/Button"
import { Status } from "../components/Status"
import { formatDate } from "../lib/format"
import { DueDate } from "./Findings"

const CARD = "rounded-xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
const H2 = "text-[15px] font-semibold"

function ControlLink({ framework, refCode }: { framework: string | null; refCode: string }) {
  const className = "font-mono text-primary hover:underline"
  if (framework === "nia-2.1") return <Link to="/nia/$ref" params={{ ref: refCode }} className={className}>{refCode}</Link>
  const code = framework === "iso42001" ? `AI ${refCode}` : refCode
  return <Link to="/controls/$code" params={{ code }} className={className}>{refCode}</Link>
}

function Alert({ error }: { error: Error | null }) {
  return error ? <p role="alert" className="text-[13px] font-medium text-bad">{error.message}</p> : null
}

export function FindingPage() {
  const { id } = useParams({ from: "/app/findings/$id" })
  const finding = useFinding(id)
  if (finding.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (finding.isError) return <p role="alert">{finding.error.message}</p>
  const f = finding.data
  const nc = isNonconformity(f.grade)
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/findings" className="hover:text-fg">Findings</Link> <span aria-hidden="true">›</span>{" "}
        <span className="font-mono">{f.code}</span>
      </nav>
      <Header f={f} />
      {f.can_edit && <DetailsEditor f={f} />}
      {nc ? <RootCause f={f} /> : <Response f={f} />}
      <Actions f={f} />
      {nc && <VerificationSection f={f} />}
      {f.can_reopen && <Reopen f={f} />}
    </div>
  )
}

function Header({ f }: { f: FindingDetail }) {
  const raise = useRaiseFindingRisk(f.id)
  return (
    <header className="rise relative grid gap-4 overflow-hidden rounded-2xl border border-line bg-surface p-6">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-1 font-mono text-[12.5px] font-semibold text-primary">{f.code} · {GRADE_LABEL[f.grade]}</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{f.title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Status area="findingGrade" value={f.grade} />
          <Status area="finding" value={f.status} />
        </div>
      </div>
      <dl className="grid gap-3 text-[13px] sm:grid-cols-4">
        <div><dt className="text-fg-3">Owner</dt><dd className="mt-0.5 font-medium">{f.owner?.full_name ?? "Unassigned"}</dd></div>
        <div><dt className="text-fg-3">Due</dt><dd className="mt-0.5"><DueDate due={f.due_date} overdue={f.overdue} /></dd></div>
        <div>
          <dt className="text-fg-3">From</dt>
          <dd className="mt-0.5">
            {f.audit ? <Link to="/audits/$id" params={{ id: f.audit.id }} className="text-primary hover:underline">{f.audit.title}</Link> : "Internal audit"}
            {f.ref && <> · <ControlLink framework={f.framework} refCode={f.ref} /></>}
          </dd>
        </div>
        <div>
          <dt className="text-fg-3">Risk register</dt>
          <dd className="mt-0.5">
            {f.risk ? (
              <Link to="/risks/$code" params={{ code: f.risk.code }} className="font-mono text-primary hover:underline">{f.risk.code}</Link>
            ) : f.can_raise_risk ? (
              <Button size="sm" variant="secondary" disabled={raise.isPending} onClick={() => raise.mutate()}>Raise as risk</Button>
            ) : (
              <span className="text-fg-3">Not raised</span>
            )}
          </dd>
        </div>
      </dl>
      {f.description && <p className="whitespace-pre-line text-[14px] text-fg-2">{f.description}</p>}
      <p className="text-[12px] text-fg-3">
        Raised {formatDate(f.raised_at)}{f.raised_by ? ` by ${f.raised_by.full_name}` : ""}
        {f.closed_at && ` · Closed ${formatDate(f.closed_at)}`}
      </p>
      <Alert error={raise.error} />
    </header>
  )
}

function PersonSelect({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  const people = usePeople()
  return (
    <label className={LABEL}>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className={FIELD}>
        <option value="">Unassigned</option>
        {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
      </select>
    </label>
  )
}

function DetailsEditor({ f }: { f: FindingDetail }) {
  const update = useUpdateFinding(f.id)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    title: f.title,
    description: f.description ?? "",
    grade: f.grade,
    owner: f.owner?.id ?? "",
    due: f.due_date ?? "",
  })
  if (!open) {
    return <div><Button size="sm" variant="secondary" onClick={() => setOpen(true)}>Edit details</Button></div>
  }
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: FindingChanges = {}
    if (form.title.trim() !== f.title) changes.title = form.title.trim()
    if (form.description.trim() !== (f.description ?? "")) changes.description = form.description.trim() || null
    if (form.grade !== f.grade) changes.grade = form.grade
    if (form.owner !== (f.owner?.id ?? "")) changes.owner_id = form.owner || null
    if (form.due !== (f.due_date ?? "")) changes.due_date = form.due || null
    update.mutate(changes, { onSuccess: () => setOpen(false) })
  }
  return (
    <form aria-label="Finding details" onSubmit={onSubmit} className={`${CARD} grid gap-3 md:grid-cols-2`}>
      <label className={`${LABEL} md:col-span-2`}>
        Title
        <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={300} className={FIELD} />
      </label>
      <label className={`${LABEL} md:col-span-2`}>
        Description
        <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} maxLength={10000} className={FIELD} />
      </label>
      <label className={LABEL}>
        Grade
        <select value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value as Grade })} className={FIELD}>
          {(Object.keys(GRADE_LABEL) as Grade[]).map((g) => <option key={g} value={g}>{GRADE_LABEL[g]}</option>)}
        </select>
      </label>
      <label className={LABEL}>
        Due date
        <input type="date" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} className={FIELD} />
      </label>
      <PersonSelect label="Owner" value={form.owner} onChange={(owner) => setForm({ ...form, owner })} />
      <div className="flex items-center gap-2 md:col-span-2">
        <Button type="submit" size="sm" disabled={update.isPending || !form.title.trim()}>Save details</Button>
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
        <Alert error={update.error} />
      </div>
    </form>
  )
}

function RootCause({ f }: { f: FindingDetail }) {
  const update = useUpdateFinding(f.id)
  const [cause, setCause] = useState(f.root_cause ?? "")
  const [correction, setCorrection] = useState(f.correction ?? "")
  if (!f.can_edit_capa) {
    return (
      <section className={`${CARD} grid gap-3`} aria-label="Root cause and correction">
        <h2 className={H2}>Root cause and correction</h2>
        <dl className="grid gap-3 text-[13.5px] md:grid-cols-2">
          <div><dt className="text-fg-3">Root cause</dt><dd className="mt-0.5 whitespace-pre-line">{f.root_cause || "Not recorded yet"}</dd></div>
          <div><dt className="text-fg-3">Correction</dt><dd className="mt-0.5 whitespace-pre-line">{f.correction || "None recorded"}</dd></div>
        </dl>
      </section>
    )
  }
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: FindingChanges = {}
    if (cause.trim() !== (f.root_cause ?? "")) changes.root_cause = cause.trim() || null
    if (correction.trim() !== (f.correction ?? "")) changes.correction = correction.trim() || null
    update.mutate(changes)
  }
  return (
    <form onSubmit={onSubmit} className={`${CARD} grid gap-3`} aria-label="Root cause and correction">
      <h2 className={H2}>Root cause and correction</h2>
      <p className="text-[12.5px] text-fg-3">Why did this happen, and what was fixed straight away? Actions below stop it happening again.</p>
      <div className="grid gap-3 md:grid-cols-2">
        <label className={LABEL}>
          Root cause
          <textarea value={cause} onChange={(e) => setCause(e.target.value)} rows={4} maxLength={10000} className={FIELD} />
        </label>
        <label className={LABEL}>
          Correction
          <textarea value={correction} onChange={(e) => setCorrection(e.target.value)} rows={4} maxLength={10000} className={FIELD} />
        </label>
      </div>
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={update.isPending}>Save root cause and correction</Button>
        {update.isSuccess && !update.isPending && <span role="status" className="text-[12.5px] text-ok">Saved</span>}
        <Alert error={update.error} />
      </div>
    </form>
  )
}

function Response({ f }: { f: FindingDetail }) {
  const close = useCloseFinding(f.id)
  const [response, setResponse] = useState(f.response ?? "")
  if (!f.can_close) {
    return (
      <section className={CARD} aria-label="Closing response">
        <h2 className={H2}>Response</h2>
        <p className="mt-2 whitespace-pre-line text-[13.5px] text-fg-2">{f.response || "No response yet."}</p>
      </section>
    )
  }
  return (
    <section className={`${CARD} grid gap-3`} aria-label="Closing response">
      <h2 className={H2}>Response</h2>
      <p className="text-[12.5px] text-fg-3">Observations and opportunities for improvement close with a response: what was done, or why no action is taken.</p>
      <label className={LABEL}>
        Response
        <textarea value={response} onChange={(e) => setResponse(e.target.value)} rows={3} maxLength={10000} className={FIELD} />
      </label>
      <div className="flex items-center gap-2">
        <Button size="sm" disabled={!response.trim() || close.isPending} onClick={() => close.mutate(response.trim())}>Close with this response</Button>
        <Alert error={close.error} />
      </div>
    </section>
  )
}

function Actions({ f }: { f: FindingDetail }) {
  return (
    <section className={`${CARD} grid gap-3`} aria-label="Corrective actions">
      <h2 className={H2}>Corrective actions</h2>
      {f.actions.length === 0 ? (
        <p className="text-[13px] text-fg-3">
          {isNonconformity(f.grade) ? "No corrective actions yet. Add at least one to plan how this will be fixed." : "No actions. They are optional for this grade."}
        </p>
      ) : (
        <ul className="grid gap-3">
          {f.actions.map((a) => <ActionItem key={a.id} findingId={f.id} a={a} />)}
        </ul>
      )}
      {f.can_add_action && <AddAction findingId={f.id} />}
    </section>
  )
}

function ActionItem({ findingId, a }: { findingId: string; a: CorrectiveAction }) {
  const update = useUpdateAction(findingId)
  const remove = useDeleteAction(findingId)
  const upload = useUploadActionFile(findingId)
  const removeFile = useDeleteActionFile(findingId)
  const [note, setNote] = useState("")
  const error = update.error ?? remove.error ?? upload.error ?? removeFile.error
  const open = a.status === "open"
  return (
    <li className="grid gap-2 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="min-w-0 text-[14px]">
          <span className="mr-2 font-mono text-[12.5px] text-fg-3">#{a.seq}</span>
          {a.description}
        </p>
        <div className="flex items-center gap-2">
          <Status area="action" value={open && a.overdue ? "overdue" : a.status} />
          {a.can_edit && open && (
            <button type="button" aria-label={`Delete action ${a.seq}`} disabled={remove.isPending} onClick={() => remove.mutate(a.id)} className="rounded px-1.5 text-fg-3 hover:bg-subtle hover:text-bad">×</button>
          )}
        </div>
      </div>
      <p className="text-[12.5px] text-fg-3">
        {a.owner?.full_name ?? "Unassigned"} · <DueDate due={a.due_date} overdue={open && a.overdue} />
        {a.done_at && ` · Done ${formatDate(a.done_at)}`}
      </p>
      {a.done_note && <p className="whitespace-pre-line text-[13px] text-fg-2">{a.done_note}</p>}
      {a.files.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {a.files.map((x) => (
            <li key={x.id} className="inline-flex items-center gap-1 rounded-md bg-subtle px-2 py-1 text-[12.5px]">
              <a href={actionFileUrl(findingId, a.id, x.id)} className="text-primary hover:underline">{x.filename}</a>
              <span className="text-fg-3">({Math.max(1, Math.round(x.size / 1024))} KB)</span>
              {a.can_complete && open && (
                <button type="button" aria-label={`Remove ${x.filename}`} onClick={() => removeFile.mutate({ actionId: a.id, fileId: x.id })} className="px-1 text-fg-3 hover:text-bad">×</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {a.can_complete && open && (
        <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <label className={LABEL}>
            What was done
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={5000} className={FIELD} />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <label className="cursor-pointer rounded-lg border border-line px-3 py-1.5 text-[13px] font-semibold text-primary hover:bg-subtle">
              Attach file
              <input
                type="file"
                aria-label={`Attach a file to action ${a.seq}`}
                className="sr-only"
                disabled={upload.isPending}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) upload.mutate({ actionId: a.id, file })
                  e.target.value = ""
                }}
              />
            </label>
            <Button
              size="sm"
              disabled={update.isPending}
              onClick={() => update.mutate({ actionId: a.id, changes: note.trim() ? { status: "done", done_note: note.trim() } : { status: "done" } })}
            >
              Mark done
            </Button>
          </div>
        </div>
      )}
      {a.can_complete && !open && (
        <div>
          <Button size="sm" variant="secondary" disabled={update.isPending} onClick={() => update.mutate({ actionId: a.id, changes: { status: "open" } })}>
            Reopen action
          </Button>
        </div>
      )}
      {upload.isPending && <p role="status" className="text-[12.5px] text-fg-3">Uploading and scanning…</p>}
      <Alert error={error} />
    </li>
  )
}

function AddAction({ findingId }: { findingId: string }) {
  const add = useAddAction(findingId)
  const [description, setDescription] = useState("")
  const [owner, setOwner] = useState("")
  const [due, setDue] = useState("")
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    add.mutate(
      { description: description.trim(), owner_id: owner || null, due_date: due || null },
      {
        onSuccess: () => {
          setDescription("")
          setOwner("")
          setDue("")
        },
      },
    )
  }
  return (
    <form aria-label="Add a corrective action" onSubmit={onSubmit} className="grid gap-3 rounded-lg bg-subtle p-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <label className={LABEL}>
        Action
        <input value={description} onChange={(e) => setDescription(e.target.value)} required maxLength={5000} className={FIELD} />
      </label>
      <PersonSelect label="Owner" value={owner} onChange={setOwner} />
      <label className={LABEL}>
        Due date
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={FIELD} />
      </label>
      <div className="flex items-center gap-2 md:col-span-3">
        <Button type="submit" size="sm" disabled={!description.trim() || add.isPending}>Add action</Button>
        <Alert error={add.error} />
      </div>
    </form>
  )
}

function VerificationSection({ f }: { f: FindingDetail }) {
  const verify = useVerifyFinding(f.id)
  const [note, setNote] = useState("")
  const waiting = f.status === "awaiting_verification"
  return (
    <section className={`${CARD} grid gap-3`} aria-label="Verification of effectiveness">
      <h2 className={H2}>Verification of effectiveness</h2>
      {f.verifications.length > 0 && (
        <ul className="grid gap-2">
          {f.verifications.map((v, i) => (
            <li key={i} className="rounded-lg bg-subtle p-3 text-[13px]">
              <p className="font-semibold">
                <span className={v.effective ? "text-ok" : "text-warn"}>{v.effective ? "Effective" : "Not effective"}</span>
                <span className="font-normal text-fg-3"> · {v.verifier?.full_name ?? "Someone"} · {formatDate(v.verified_at)}</span>
              </p>
              <p className="mt-1 whitespace-pre-line text-fg-2">{v.note}</p>
            </li>
          ))}
        </ul>
      )}
      {waiting && f.can_verify && (
        <div className="grid gap-2">
          <label className={LABEL}>
            What you checked
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={5000} className={FIELD} />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={!note.trim() || verify.isPending} onClick={() => verify.mutate({ effective: true, note: note.trim() })}>
              Effective: close the finding
            </Button>
            <Button size="sm" variant="secondary" disabled={!note.trim() || verify.isPending} onClick={() => verify.mutate({ effective: false, note: note.trim() })}>
              Not effective: more work needed
            </Button>
            <Alert error={verify.error} />
          </div>
        </div>
      )}
      {waiting && !f.can_verify && (
        <p className="text-[13px] text-fg-2">
          Every corrective action is done. An ISMS manager or internal auditor, someone who did not own this finding or its actions, now checks that they worked.
        </p>
      )}
      {!waiting && f.status !== "closed" && (
        <p className="text-[13px] text-fg-3">Verification opens once the root cause is recorded and every corrective action is done.</p>
      )}
    </section>
  )
}

function Reopen({ f }: { f: FindingDetail }) {
  const reopen = useReopenFinding(f.id)
  const [reason, setReason] = useState("")
  return (
    <section className={`${CARD} grid gap-2`} aria-label="Reopen">
      <label className={LABEL}>
        Why reopen?
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} className={FIELD} />
      </label>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" disabled={!reason.trim() || reopen.isPending} onClick={() => reopen.mutate(reason.trim())}>Reopen finding</Button>
        <Alert error={reopen.error} />
      </div>
    </section>
  )
}
