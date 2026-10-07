import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import { IMPLEMENTATION_LABEL, useControl, useUpdateControl } from "../api/controls"
import type { ControlDetail as Detail } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"

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
        </div>
        <StatusPill status={c.status} />
      </header>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_300px]">
        <div className="grid content-start gap-4">
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Evidence</h2>
            <ul>
              {c.slots.map((s) => (
                <li
                  key={s.id}
                  className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5 last:border-0"
                >
                  <div className="min-w-0">
                    <p className="font-semibold">{s.name}</p>
                    <p className="text-[12.5px] text-fg-3">
                      <span>{s.evidence_type}</span>
                      {s.freshness_days ? <span aria-hidden="true"> · </span> : null}
                      {s.freshness_days ? <span>Refresh every {s.freshness_days} days</span> : null}
                    </p>
                  </div>
                  <StatusPill status="not_started" />
                </li>
              ))}
            </ul>
          </section>
          <ImplementationSection control={c} canEdit={canEdit} />
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
