import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import { type NiaDetail, type NiaLink, useNiaControl, useSetNiaApplicability, useSetNiaMapping } from "../api/nia"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { DocumentSections } from "../components/DocumentSections"
import { StatusPill } from "../components/StatusPill"

const CARD = "rounded-xl border border-line bg-surface p-5"
const LABEL = "mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3"

export function NiaControlPage() {
  const { ref } = useParams({ from: "/app/nia/$ref" })
  const control = useNiaControl(ref)
  if (control.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (control.isError) return <p role="alert">{control.error.message}</p>
  const c = control.data
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/controls" search={{ framework: "nia" }} className="hover:text-fg">NIA controls</Link>{" "}
        <span aria-hidden="true">›</span>{" "}
        <Link to="/controls" search={{ framework: "nia", domain: c.domain }} className="hover:text-fg">{c.domain_name}</Link>{" "}
        <span aria-hidden="true">›</span> <ControlId code={c.ref} />
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">
            NIA v2.1 · {c.ref} · {c.domain_name}
          </p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{c.title}</h1>
          <p className="mt-2 flex flex-wrap gap-2 text-[12.5px]">
            {c.mandatory && <span className="rounded-full bg-primary-soft px-2.5 py-0.5 font-semibold text-primary">Mandatory</span>}
            {c.own_control && <span className="rounded-full border border-line px-2.5 py-0.5 font-medium text-fg-2">NIA only</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {c.score !== null && <span className="text-[13px] tabular-nums text-fg-2">Score {Math.round(c.score)}</span>}
          {c.applicable ? <StatusPill status={c.status} /> : <StatusPill status="excluded" label="Not applicable" />}
        </div>
      </header>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid content-start gap-4">
          <Statement control={c} />
          <MappedControls control={c} />
          {c.own_control ? (
            <DocumentSections codes={c.mapped.map((m) => m.code)} linkTo={c.own_control} canLink={c.can_edit} />
          ) : (
            <DocumentSections
              codes={c.mapped.map((m) => m.code)}
              canLink={false}
              hint="Documents linked to the mapped ISO controls. Link new documents on those control pages."
            />
          )}
        </div>
        <aside className="grid content-start gap-4">
          <Applicability control={c} />
        </aside>
      </div>
    </div>
  )
}

function Statement({ control }: { control: NiaDetail }) {
  return (
    <section className={CARD} aria-labelledby="statement-title">
      <h2 id="statement-title" className={LABEL}>{control.text ? "Control statement (NCSA)" : "What this domain covers"}</h2>
      {control.text ? (
        <p className="whitespace-pre-line text-[14px] leading-relaxed">{control.text}</p>
      ) : (
        <>
          <p className="text-[14px] leading-relaxed text-fg-2">{control.summary ?? "No summary yet."}</p>
          <p className="mt-3 rounded-lg bg-subtle px-3 py-2 text-[12.5px] text-fg-3">
            The official text has not been imported. An ISMS manager can import it on the Compliance page from your copy of the NCSA standard.
          </p>
        </>
      )}
    </section>
  )
}

function MappedControls({ control }: { control: NiaDetail }) {
  const save = useSetNiaMapping(control.ref)
  const initial = (): NiaLink[] => control.mapped.map((m) => ({ code: m.code, coverage: m.coverage }))
  const [links, setLinks] = useState<NiaLink[]>(initial)
  const [code, setCode] = useState("")
  const [coverage, setCoverage] = useState<NiaLink["coverage"]>("full")
  useEffect(() => setLinks(initial()), [control]) // eslint-disable-line react-hooks/exhaustive-deps
  const byCode = new Map(control.mapped.map((m) => [m.code, m]))
  const dirty = JSON.stringify(links) !== JSON.stringify(initial())

  function add(event: FormEvent) {
    event.preventDefault()
    const next = code.trim().toUpperCase()
    if (!next || links.some((l) => l.code === next)) return
    setLinks([...links, { code: next, coverage }])
    setCode("")
  }

  return (
    <section className={CARD} aria-label="Mapped ISO controls">
      <h2 className="mb-1 text-[15px] font-semibold">Mapped ISO controls</h2>
      <p className="mb-3 text-[13px] text-fg-3">
        Evidence is shared: this NIA control is only as far along as the ISO controls it maps to.
      </p>
      {links.length === 0 ? (
        <p className="text-[13px] text-fg-3">No controls in the mapping.</p>
      ) : (
        <ul className="grid gap-1">
          {links.map((l) => {
            const m = byCode.get(l.code)
            return (
              <li key={l.code} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-subtle">
                <Link to="/controls/$code" params={{ code: l.code }} className="min-w-0 flex-1 truncate text-[13.5px] hover:text-primary">
                  <ControlId code={l.code} /> {l.code.startsWith("NIA ") ? "Own NIA control (its own evidence)" : (m?.title ?? "Not saved yet")}
                </Link>
                {l.coverage === "partial" && <span className="text-[12px] text-fg-3">Partial</span>}
                {m && <StatusPill status={m.status} />}
                {control.can_edit && (
                  <button
                    type="button"
                    aria-label={`Remove ${l.code}`}
                    onClick={() => setLinks(links.filter((x) => x.code !== l.code))}
                    className="rounded px-1.5 text-fg-3 hover:bg-surface hover:text-fg"
                  >
                    ×
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {control.can_edit && (
        <div className="mt-4 grid gap-3 border-t border-line pt-4">
          <form onSubmit={add} className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1 text-[12.5px] text-fg-2">
              ISO control
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="A.5.1"
                className="w-28 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 font-mono text-[13px]"
              />
            </label>
            <label className="grid gap-1 text-[12.5px] text-fg-2">
              Coverage
              <select
                value={coverage}
                onChange={(e) => setCoverage(e.target.value as NiaLink["coverage"])}
                className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
              >
                <option value="full">Full</option>
                <option value="partial">Partial</option>
              </select>
            </label>
            <Button type="submit" variant="secondary" size="sm">Add</Button>
          </form>
          <div className="flex items-center gap-3">
            <Button size="sm" disabled={!dirty || links.length === 0 || save.isPending} onClick={() => save.mutate(links)}>
              {save.isPending ? "Saving…" : "Save mapping"}
            </Button>
            {links.length === 0 && (
              <p className="text-[12.5px] text-fg-3">Keep at least one control. If this NIA control does not apply, mark it not applicable.</p>
            )}
            {save.isError && <p role="alert" className="text-[13px] text-bad">{save.error.message}</p>}
          </div>
        </div>
      )}
    </section>
  )
}

function Applicability({ control }: { control: NiaDetail }) {
  const save = useSetNiaApplicability(control.ref)
  const [applies, setApplies] = useState(control.applicable)
  const [reason, setReason] = useState("")
  useEffect(() => setApplies(control.applicable), [control.applicable])
  const changed = applies !== control.applicable
  const needsReason = !applies && changed && !reason.trim()

  return (
    <section className={CARD} aria-labelledby="applicability-title">
      <h2 id="applicability-title" className={LABEL}>Applicability</h2>
      {!control.applicable && control.exclusion_reason && (
        <p className="mb-3 text-[13px] text-fg-2">Not applicable: {control.exclusion_reason}</p>
      )}
      {control.applicable && !control.can_edit && <p className="text-[13px] text-fg-2">This control applies to us.</p>}
      {control.can_edit && (
        <div className="grid gap-3">
          <label className="flex items-center gap-2 text-[13.5px]">
            <input type="checkbox" checked={applies} onChange={(e) => setApplies(e.target.checked)} className="h-4 w-4 accent-[var(--primary)]" />
            This control applies to us
          </label>
          {!applies && changed && (
            <label className="grid gap-1 text-[12.5px] text-fg-2">
              Why it does not apply
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                maxLength={2000}
                className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] text-fg"
              />
            </label>
          )}
          {changed && (
            <Button
              size="sm"
              disabled={needsReason || save.isPending}
              onClick={() =>
                save.mutate(applies ? { applicable: true } : { applicable: false, reason: reason.trim() }, {
                  onSuccess: () => setReason(""),
                })
              }
            >
              Save applicability
            </Button>
          )}
          {save.isError && <p role="alert" className="text-[13px] text-bad">{save.error.message}</p>}
        </div>
      )}
    </section>
  )
}
