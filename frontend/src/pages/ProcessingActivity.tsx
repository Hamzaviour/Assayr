import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import { useAssets } from "../api/assets"
import { usePeople } from "../api/people"
import {
  ACTIVITY_STATUS,
  type Activity,
  type ActivityInput,
  DATA_SUBJECTS,
  LAWFUL_BASIS,
  useActivity,
  useLinkActivityAssets,
  useUpdateActivity,
} from "../api/privacy"
import { Button } from "../components/Button"
import { LevelBadge } from "../components/LevelBadge"
import { PII_CATEGORIES, SENSITIVE } from "../lib/privacy"
import { STATUS_TONE, Tag } from "./Privacy"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"

export function ProcessingActivityPage() {
  const { id } = useParams({ from: "/app/privacy/$id" })
  const activity = useActivity(id)
  if (activity.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (activity.isError) return <p role="alert">{activity.error.message}</p>
  const a = activity.data
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/privacy" className="hover:text-fg">Data privacy</Link> <span aria-hidden="true">›</span> {a.code}
      </nav>
      <header className="rise relative flex flex-wrap items-start justify-between gap-3 overflow-hidden rounded-2xl border border-line bg-surface p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
        <div>
          <p className="mb-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-fg-3">Processing activity</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{a.code} · {a.name}</h1>
        </div>
        <span className="flex flex-wrap gap-1.5">
          <Tag tone={STATUS_TONE[a.status]}>{ACTIVITY_STATUS[a.status] ?? a.status}</Tag>
          {a.sensitive && <Tag tone="bg-bad-soft text-bad border-bad/25">Sensitive</Tag>}
          {a.cross_border && <Tag tone="bg-warn-soft text-warn border-warn/25">Cross-border</Tag>}
          {a.review_overdue && <Tag tone="bg-bad text-white border-bad">Review due</Tag>}
        </span>
      </header>
      <ActivityForm activity={a} />
      <StoredOn activity={a} />
    </div>
  )
}

function toggle(list: string[], value: string, on: boolean) {
  return on ? [...list, value] : list.filter((x) => x !== value)
}

function ActivityForm({ activity: a }: { activity: Activity }) {
  const update = useUpdateActivity(a.id)
  const people = usePeople()
  const [form, setForm] = useState<ActivityInput>(() => ({
    name: a.name,
    purpose: a.purpose,
    data_subjects: a.data_subjects,
    data_categories: a.data_categories,
    lawful_basis: a.lawful_basis,
    recipients: a.recipients,
    cross_border: a.cross_border,
    transfer_countries: a.transfer_countries,
    retention: a.retention,
    security_measures: a.security_measures,
    owner_id: a.owner?.id ?? null,
    status: a.status,
    review_due: a.review_due,
  }))
  const [saved, setSaved] = useState(false)
  useEffect(() => setSaved(false), [form])
  const set = <K extends keyof ActivityInput>(key: K, value: ActivityInput[K]) => setForm((f) => ({ ...f, [key]: value }))
  const text = (key: "purpose" | "recipients" | "transfer_countries" | "retention" | "security_measures") => (e: { target: { value: string } }) =>
    set(key, e.target.value || null)
  const disabled = !a.can_edit

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    update.mutate(form, { onSuccess: () => setSaved(true) })
  }

  return (
    <form onSubmit={onSubmit} className={`${CARD} grid gap-4`}>
      <fieldset disabled={disabled} className="grid gap-4 md:grid-cols-2">
        <label className={LABEL}>
          Name
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={200} className={FIELD} />
        </label>
        <label className={LABEL}>
          Lawful basis
          <select value={form.lawful_basis} onChange={(e) => set("lawful_basis", e.target.value)} className={FIELD}>
            {Object.entries(LAWFUL_BASIS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={`${LABEL} md:col-span-2`}>
          Purpose
          <textarea rows={2} value={form.purpose ?? ""} onChange={text("purpose")} maxLength={5000} className={FIELD} />
        </label>
        <fieldset className="grid gap-2 md:col-span-2">
          <legend className="mb-1 text-[12.5px] font-medium text-fg-2">Whose data</legend>
          <div className="flex flex-wrap gap-2">
            {Object.entries(DATA_SUBJECTS).map(([code, label]) => (
              <label key={code} className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[12.5px]">
                <input type="checkbox" checked={form.data_subjects.includes(code)} onChange={(e) => set("data_subjects", toggle(form.data_subjects, code, e.target.checked))} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset className="grid gap-2 md:col-span-2">
          <legend className="mb-1 text-[12.5px] font-medium text-fg-2">Personal data</legend>
          <div className="flex flex-wrap gap-2">
            {Object.entries(PII_CATEGORIES).map(([code, label]) => (
              <label
                key={code}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12.5px] ${SENSITIVE.has(code) ? "border-bad/30" : "border-line"}`}
              >
                <input type="checkbox" checked={form.data_categories.includes(code)} onChange={(e) => set("data_categories", toggle(form.data_categories, code, e.target.checked))} />
                {label}
                {SENSITIVE.has(code) && <span className="text-[10.5px] font-bold text-bad">sensitive</span>}
              </label>
            ))}
          </div>
        </fieldset>
        <label className={LABEL}>
          Shared with (recipients)
          <input value={form.recipients ?? ""} onChange={text("recipients")} maxLength={2000} className={FIELD} />
        </label>
        <label className={LABEL}>
          Retention
          <input value={form.retention ?? ""} onChange={text("retention")} placeholder="e.g. 7 years after leaving" maxLength={300} className={FIELD} />
        </label>
        <label className="flex items-center gap-2 text-[13px]">
          <input type="checkbox" checked={form.cross_border} onChange={(e) => set("cross_border", e.target.checked)} />
          Data is transferred outside Qatar
        </label>
        {form.cross_border && (
          <label className={LABEL}>
            Destination countries
            <input value={form.transfer_countries ?? ""} onChange={text("transfer_countries")} maxLength={300} className={FIELD} />
          </label>
        )}
        <label className={`${LABEL} md:col-span-2`}>
          Security measures
          <textarea rows={2} value={form.security_measures ?? ""} onChange={text("security_measures")} maxLength={5000} className={FIELD} />
        </label>
        <label className={LABEL}>
          Owner
          <select value={form.owner_id ?? ""} onChange={(e) => set("owner_id", e.target.value || null)} className={FIELD}>
            <option value="">Unassigned</option>
            {a.owner && !(people.data ?? []).some((p) => p.id === a.owner?.id) && <option value={a.owner.id}>{a.owner.full_name}</option>}
            {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className={LABEL}>
            Status
            <select value={form.status} onChange={(e) => set("status", e.target.value)} className={FIELD}>
              {Object.entries(ACTIVITY_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className={LABEL}>
            Next review
            <input type="date" value={form.review_due ?? ""} onChange={(e) => set("review_due", e.target.value || null)} className={FIELD} />
          </label>
        </div>
      </fieldset>
      {a.can_edit && (
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!form.name.trim() || update.isPending}>Save activity</Button>
          {saved && <span role="status" className="text-[13px] font-medium text-ok">Saved</span>}
          {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
        </div>
      )}
    </form>
  )
}

function StoredOn({ activity: a }: { activity: Activity }) {
  const assets = useAssets()
  const link = useLinkActivityAssets(a.id)
  const [chosen, setChosen] = useState<string[]>(a.assets.map((x) => x.id))
  const all = assets.data ?? []
  const newlyMarked = all.filter((x) => chosen.includes(x.id) && !x.holds_pii)

  return (
    <section aria-label="Where the data is kept" className={`${CARD} grid gap-3`}>
      <h2 className="text-[15px] font-semibold">Where the data is kept</h2>
      <p className="text-[12.5px] text-fg-3">Choose the assets that store or process this personal data.</p>
      <ul className="grid gap-1.5 md:grid-cols-2">
        {all.map((x) => (
          <li key={x.id}>
            <label className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
              <input
                type="checkbox"
                disabled={!a.can_edit}
                checked={chosen.includes(x.id)}
                onChange={(e) => setChosen(toggle(chosen, x.id, e.target.checked))}
              />
              <span className="font-mono text-[12px] text-fg-3">{x.code}</span>
              <span className="flex-1">{x.name}</span>
              <LevelBadge level={x.criticality} />
            </label>
          </li>
        ))}
      </ul>
      {newlyMarked.length > 0 && (
        <p className="text-[12.5px] text-warn">
          {newlyMarked.map((x) => x.name).join(", ")} will be marked as holding personal data.
        </p>
      )}
      {a.can_edit && (
        <div className="flex items-center gap-3">
          <Button size="sm" disabled={link.isPending} onClick={() => link.mutate(chosen)}>Save assets</Button>
          {link.isError && <p role="alert" className="text-[13px] text-bad">{link.error.message}</p>}
        </div>
      )}
    </section>
  )
}
