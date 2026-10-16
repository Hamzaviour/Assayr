import { Link, useParams } from "@tanstack/react-router"
import { useQueryClient } from "@tanstack/react-query"
import { type DragEvent, type FormEvent, useCallback, useEffect, useState } from "react"
import { IMPLEMENTATION_LABEL, useControl, useUpdateControl } from "../api/controls"
import { useAttest, useUploadEvidence } from "../api/evidence"
import type { ControlDetail as Detail, EvidenceSlot as Slot } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { DocumentSections } from "../components/DocumentSections"
import { Icon } from "../components/icons"
import { SlotStatePill } from "../components/SlotStatePill"
import { StatusPill } from "../components/StatusPill"
import { VerificationPanel } from "../components/VerificationPanel"
import { formatDate } from "../lib/format"

export function ControlDetailPage() {
  const { code } = useParams({ from: "/app/controls/$code" })
  const control = useControl(code)
  const me = useMe()

  if (control.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (control.isError) return <p role="alert">{control.error.message}</p>
  const c = control.data
  const perms = me.data?.permissions ?? []
  const canEdit =
    perms.includes("controls:write") || (perms.includes("controls:write_own") && c.owner?.id === me.data?.id)

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/controls" className="hover:text-fg">Controls</Link> <span aria-hidden="true">›</span>{" "}
        <ControlId code={c.code} />
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">{c.code} · {c.theme} controls</p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{c.title}</h1>
          <p className="mt-2 text-[13px] text-fg-2">
            Owner: {c.owner?.full_name ?? `Unassigned (suggested: ${c.default_owner_role ?? "ISMS manager"})`} · Review:{" "}
            {c.review_frequency?.toLowerCase() ?? "not set"}
          </p>
          <AttestationLine control={c} canEdit={canEdit} />
        </div>
        <div className="flex items-center gap-2">
          {c.score !== null && <span className="text-[13px] text-fg-2 tabular-nums">Score {Math.round(c.score)}</span>}
          <StatusPill status={c.status} />
        </div>
      </header>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_300px]">
        <div className="grid content-start gap-4">
          <EvidenceSlots control={c} canEdit={canEdit} />
          <ImplementationSection control={c} canEdit={canEdit} />
          <DocumentSections codes={[c.code]} linkTo={c.code} canLink={canEdit} />
        </div>
        <aside className="grid content-start gap-4">
          <section className="rounded-xl border border-line bg-surface p-5">
            <h3 className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">What auditors look for</h3>
            <p className="text-[13px] text-fg-2">{c.description}</p>
          </section>
          <section className="rounded-xl border border-line bg-surface p-5">
            <h3 className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Maps to</h3>
            <ul className="grid gap-1 text-[13px]">
              {c.requirements.map((r) => (
                <li key={r.ref}><ControlId code={r.ref} /> {r.title}</li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ImplementationSection({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const update = useUpdateControl(control.code)
  const [status, setStatus] = useState(control.implementation_status)
  const [text, setText] = useState(control.implementation_text ?? "")
  const [saved, setSaved] = useState(false)

  useEffect(() => setSaved(false), [status, text])

  if (!canEdit) {
    return (
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="mb-2 text-[15px] font-semibold">How we do it</h2>
        <p className="text-fg-2">{control.implementation_text || "Not described yet."}</p>
        <p className="mt-2 text-[13px] text-fg-3">{IMPLEMENTATION_LABEL[control.implementation_status]}</p>
      </section>
    )
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: { implementation_status?: string; implementation_text?: string | null } = {}
    if (status !== control.implementation_status) changes.implementation_status = status
    if (text !== (control.implementation_text ?? "")) changes.implementation_text = text || null
    await update.mutateAsync(changes)
    setSaved(true)
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3 rounded-xl border border-line bg-surface p-5">
      <label htmlFor="impl-text" className="text-[15px] font-semibold">How we do it</label>
      <textarea
        id="impl-text"
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
      />
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="impl-status" className="text-[13px] text-fg-2">Implementation status</label>
        <select
          id="impl-status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
        >
          {Object.entries(IMPLEMENTATION_LABEL).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <Button type="submit" className="ml-auto" disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      {saved && <p role="status" className="text-[13px] text-ok">Saved</p>}
    </form>
  )
}

function EvidenceSlots({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const upload = useUploadEvidence(control.code)
  const queryClient = useQueryClient()
  const [active, setActive] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["control", control.code] })
    queryClient.invalidateQueries({ queryKey: ["readiness"] })
  }, [queryClient, control.code])

  async function send(slotId: string, file: File, evidenceDate: string) {
    setErrors((e) => ({ ...e, [slotId]: "" }))
    try {
      const link = await upload.mutateAsync({ slotId, file, evidenceDate })
      setActive((a) => ({ ...a, [slotId]: link.id }))
    } catch (err) {
      setErrors((e) => ({ ...e, [slotId]: err instanceof Error ? err.message : "Upload failed." }))
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
        <h2 className="text-[15px] font-semibold">Evidence</h2>
        {canEdit && <span className="text-[12.5px] text-fg-3">Drop a file on a slot, or use Upload</span>}
      </div>
      <ul>
        {control.slots.map((slot) => (
          <SlotRow key={slot.id} slot={slot} canEdit={canEdit} onFile={(f, d) => send(slot.id, f, d)}
            activeLinkId={active[slot.id]} error={errors[slot.id]} onDone={refresh} />
        ))}
      </ul>
    </section>
  )
}

function SlotRow({ slot, canEdit, onFile, activeLinkId, error, onDone }: {
  slot: Slot
  canEdit: boolean
  onFile: (file: File, evidenceDate: string) => void
  activeLinkId?: string
  error?: string
  onDone: () => void
}) {
  const [over, setOver] = useState(false)
  const [evidenceDate, setEvidenceDate] = useState("")
  const meta = [
    slot.evidence_type,
    slot.freshness_days ? `Refresh every ${slot.freshness_days} days` : null,
    slot.artefact?.filename,
    slot.artefact?.expires_on ? `expires ${formatDate(slot.artefact.expires_on)}` : null,
  ].filter(Boolean)

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    if (file && canEdit) onFile(file, evidenceDate)
  }

  return (
    <li
      className={`border-b border-line last:border-0 ${over ? "bg-primary-soft" : ""}`}
      onDragOver={(e) => { if (canEdit) { e.preventDefault(); setOver(true) } }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
        <div className="min-w-0">
          <p className="font-semibold">{slot.name}</p>
          <p className="text-[12.5px] text-fg-3">
            {meta.map((m, i) => <span key={i}>{i > 0 && <span aria-hidden="true"> · </span>}{m}</span>)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SlotStatePill state={slot.state} artefactState={slot.artefact?.state} />
          {canEdit && (
            <input type="date" value={evidenceDate} max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setEvidenceDate(e.target.value)}
              aria-label={`Evidence date for ${slot.name} (optional)`} title="Evidence date (optional)"
              className="h-7 rounded-lg border border-line-2 bg-surface px-2 text-[12.5px] text-fg-2" />
          )}
          {canEdit && (
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3">
              <Icon name="upload" size={14} />
              {slot.artefact ? "New version" : "Upload"}
              <input type="file" className="sr-only" aria-label={`Upload evidence for ${slot.name}`}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f, evidenceDate); e.target.value = "" }} />
            </label>
          )}
        </div>
      </div>
      {activeLinkId && <VerificationPanel linkId={activeLinkId} onDone={onDone} />}
      {error && <p role="alert" className="px-5 pb-3 text-[13px] text-bad">{error}</p>}
    </li>
  )
}

function AttestationLine({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const attest = useAttest(control.code)
  const [open, setOpen] = useState(false)
  const [statement, setStatement] = useState("This control operates as described.")
  const a = control.attestation

  async function confirm() {
    await attest.mutateAsync(statement.trim())
    setOpen(false)
  }

  return (
    <div className="mt-2 grid gap-2 text-[13px] text-fg-2">
      <p>
        {a ? `Attested by ${a.by ?? "unknown"} on ${formatDate(a.attested_at)}, valid until ${formatDate(a.valid_until)}`
           : "Not attested yet"}
        {canEdit && !open && (
          <Button variant="ghost" size="sm" className="ml-2" onClick={() => setOpen(true)}>Attest</Button>
        )}
      </p>
      {open && (
        <div className="grid max-w-xl gap-2">
          <label htmlFor="attest-statement" className="font-medium text-fg">Statement</label>
          <textarea id="attest-statement" rows={2} value={statement} onChange={(e) => setStatement(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm" />
          {attest.isError && <p role="alert" className="text-bad">{attest.error.message}</p>}
          <div className="flex gap-2">
            <Button size="sm" onClick={confirm} disabled={attest.isPending || !statement.trim()}>Confirm attestation</Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  )
}
