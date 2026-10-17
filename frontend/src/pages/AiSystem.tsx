import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import {
  type Assessment,
  type SectionKey,
  SECTIONS,
  SOURCE_LABEL,
  useAddImpact,
  useAiSystem,
  useAssessment,
  useAssessmentAction,
  useRaiseImpact,
  useSaveAssessment,
} from "../api/ai"
import { Button } from "../components/Button"
import { LEVEL_COLOR, LEVEL_LABEL, LevelBadge } from "../components/LevelBadge"
import { Status } from "../components/Status"
import { formatDate } from "../lib/format"
import { FIELD, LABEL, LIFECYCLE_LABEL } from "./AiSystems"

const AREAS = SECTIONS.filter(([key]) => key !== "conclusion")

export function AiSystemPage() {
  const { id } = useParams({ from: "/app/ai/$id" })
  const system = useAiSystem(id)
  if (system.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (system.isError) return <p role="alert">{system.error.message}</p>
  const s = system.data
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/ai" className="hover:text-fg">AI systems</Link> <span aria-hidden="true">›</span>{" "}
        <span className="font-mono">{s.code}</span>
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">{s.code} · {SOURCE_LABEL[s.source]}{s.provider ? ` · ${s.provider}` : ""}</p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{s.name}</h1>
          {s.purpose && <p className="mt-2 max-w-2xl text-[14px] text-fg-2">{s.purpose}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Status area="aiLifecycle" value={s.lifecycle} label={LIFECYCLE_LABEL[s.lifecycle]} />
          <LevelBadge level={s.risk_level} />
        </div>
      </header>
      <dl className="grid gap-3 rounded-xl border border-line bg-surface p-5 text-[13px] sm:grid-cols-3">
        <div><dt className="text-fg-3">Owner</dt><dd className="mt-0.5 font-medium">{s.owner?.full_name ?? "Unassigned"}</dd></div>
        <div><dt className="text-fg-3">Model type</dt><dd className="mt-0.5 font-medium">{s.model_type ?? "Not recorded"}</dd></div>
        <div><dt className="text-fg-3">Personal data</dt><dd className="mt-0.5 font-medium">{s.uses_personal_data ? s.pii_categories.join(", ") || "Yes" : "No"}</dd></div>
      </dl>
      <AssessmentSection id={id} canEdit={s.can_edit} />
    </div>
  )
}

function AssessmentSection({ id, canEdit }: { id: string; canEdit: boolean }) {
  const assessment = useAssessment(id)
  const save = useSaveAssessment(id)
  if (assessment.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (assessment.isError) return <p role="alert">{assessment.error.message}</p>
  if (assessment.data === null) {
    return (
      <section className="rounded-xl border border-dashed border-line-2 bg-surface p-6 text-center">
        <h2 className="text-[16px] font-semibold">AI system impact assessment</h2>
        <p className="mt-1 text-[13.5px] text-fg-2">No impact assessment yet.</p>
        {canEdit && (
          <Button className="mt-3" onClick={() => save.mutate({})} disabled={save.isPending}>Start assessment</Button>
        )}
        {save.isError && <p role="alert" className="mt-2 text-[13px] text-bad">{save.error.message}</p>}
      </section>
    )
  }
  return <AssessmentEditor id={id} a={assessment.data} canEdit={canEdit && assessment.data.can_edit} />
}

function AssessmentEditor({ id, a, canEdit }: { id: string; a: Assessment; canEdit: boolean }) {
  const save = useSaveAssessment(id)
  const action = useAssessmentAction(id)
  const editable = canEdit && a.status !== "approved"
  const [draft, setDraft] = useState<Partial<Record<SectionKey, string>>>({})
  const dirty = Object.keys(draft).length > 0
  function onSave(event: FormEvent) {
    event.preventDefault()
    save.mutate(draft, { onSuccess: () => setDraft({}) })
  }
  return (
    <section className="grid gap-4 rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[16px] font-semibold">AI system impact assessment</h2>
          {a.status === "approved" && a.approved_by && (
            <p className="text-[12.5px] text-fg-3">
              Approved by {a.approved_by.full_name}{a.approved_at ? ` on ${formatDate(a.approved_at)}` : ""}
              {a.review_due ? ` · review by ${formatDate(a.review_due)}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Status area="aiia" value={a.status} />
          {canEdit && a.status === "draft" && (
            <Button size="sm" onClick={() => action.mutate("submit")} disabled={action.isPending || dirty}>Submit for review</Button>
          )}
          {canEdit && a.status === "in_review" && (
            <Button size="sm" onClick={() => action.mutate("approve")} disabled={action.isPending}>Approve</Button>
          )}
          {canEdit && a.status !== "draft" && (
            <Button size="sm" variant="secondary" onClick={() => action.mutate("reopen")} disabled={action.isPending}>Reopen</Button>
          )}
        </div>
      </div>
      {action.isError && <p role="alert" className="rounded-lg bg-bad-soft px-3 py-2 text-[13px] text-bad">{action.error.message}</p>}
      <form onSubmit={onSave} className="grid gap-3 md:grid-cols-2">
        {SECTIONS.map(([key, label]) => (
          <label key={key} className={`${LABEL} ${key === "conclusion" ? "md:col-span-2" : ""}`}>
            {label}
            <textarea
              value={draft[key] ?? a[key] ?? ""}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              readOnly={!editable}
              rows={3}
              maxLength={10000}
              className={FIELD}
            />
          </label>
        ))}
        {editable && (
          <div className="flex items-center gap-2 md:col-span-2">
            <Button type="submit" size="sm" variant="secondary" disabled={!dirty || save.isPending}>Save sections</Button>
            {a.missing.length > 0 && <p className="text-[12.5px] text-fg-3">Still to fill in: {a.missing.join(", ")}.</p>}
            {save.isError && <p role="alert" className="text-[13px] text-bad">{save.error.message}</p>}
          </div>
        )}
      </form>
      <Impacts id={id} a={a} canAdd={editable} canRaise={canEdit} />
    </section>
  )
}

function Impacts({ id, a, canAdd, canRaise }: { id: string; a: Assessment; canAdd: boolean; canRaise: boolean }) {
  const add = useAddImpact(id)
  const raise = useRaiseImpact(id)
  const [form, setForm] = useState({ area: "fairness", description: "", likelihood: 3, impact: 3 })
  function onAdd(event: FormEvent) {
    event.preventDefault()
    add.mutate({ ...form, description: form.description.trim() }, { onSuccess: () => setForm({ ...form, description: "" }) })
  }
  const areaLabel = Object.fromEntries(SECTIONS) as Record<string, string>
  return (
    <div className="grid gap-3">
      <h3 className="text-[14px] font-semibold">Impacts</h3>
      {a.impacts.length === 0 && <p className="text-[13px] text-fg-3">No impacts recorded yet.</p>}
      {a.impacts.length > 0 && (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-fg-3">
              {["Area", "Impact", "L", "I", "Score", "Risk register"].map((h) => <th key={h} className="px-2 py-2 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {a.impacts.map((i) => (
              <tr key={i.id} className="border-t border-line">
                <td className="whitespace-nowrap px-2 py-2 text-fg-2">{areaLabel[i.area] ?? i.area}</td>
                <td className="min-w-48 px-2 py-2">{i.description}</td>
                <td className="px-2 py-2 tabular-nums">{i.likelihood}</td>
                <td className="px-2 py-2 tabular-nums">{i.impact}</td>
                <td className="px-2 py-2">
                  <span className="inline-flex min-w-8 justify-center rounded-md px-1.5 py-0.5 text-[12px] font-semibold tabular-nums text-white"
                    style={{ background: LEVEL_COLOR[i.level] }} title={LEVEL_LABEL[i.level]}>
                    {i.score}
                  </span>
                </td>
                <td className="whitespace-nowrap px-2 py-2">
                  {i.risk_code ? (
                    <Link to="/risks/$code" params={{ code: i.risk_code }} className="font-mono text-[12.5px] font-semibold text-primary hover:underline">{i.risk_code}</Link>
                  ) : canRaise ? (
                    <Button size="sm" variant="secondary" onClick={() => raise.mutate(i.id)} disabled={raise.isPending}>Raise to risk register</Button>
                  ) : (
                    <span className="text-fg-3">Not raised</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {raise.isError && <p role="alert" className="text-[13px] text-bad">{raise.error.message}</p>}
      {canAdd && (
        <form onSubmit={onAdd} aria-label="Add an impact" className="grid gap-2 rounded-lg bg-subtle p-3 md:grid-cols-[180px_minmax(0,1fr)_110px_110px_auto] md:items-end">
          <label className={LABEL}>
            Area
            <select value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} className={FIELD}>
              {AREAS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className={LABEL}>
            Description
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={500} className={FIELD} />
          </label>
          <label className={LABEL}>
            Likelihood
            <select value={form.likelihood} onChange={(e) => setForm({ ...form, likelihood: Number(e.target.value) })} className={FIELD}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className={LABEL}>
            Impact
            <select value={form.impact} onChange={(e) => setForm({ ...form, impact: Number(e.target.value) })} className={FIELD}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <Button type="submit" size="sm" disabled={!form.description.trim() || add.isPending}>Add impact</Button>
          {add.isError && <p role="alert" className="text-[13px] text-bad md:col-span-5">{add.error.message}</p>}
        </form>
      )}
    </div>
  )
}
