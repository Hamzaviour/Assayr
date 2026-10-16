import { type FormEvent, useState } from "react"
import { type Processor, type ProcessorInput, useCreateProcessor, useProcessors, useUpdateProcessor } from "../../api/privacy2"
import { Button } from "../../components/Button"
import { LevelBadge } from "../../components/LevelBadge"
import { formatDate } from "../../lib/format"
import { PII_CATEGORIES } from "../../lib/privacy"
import { CategoryChips, Tag } from "../Privacy"

const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
const RESULT: Record<string, [string, string]> = {
  satisfactory: ["Satisfactory", "bg-ok-soft text-ok border-ok/25"],
  concerns: ["Concerns", "bg-warn-soft text-warn border-warn/25"],
  unsatisfactory: ["Unsatisfactory", "bg-bad-soft text-bad border-bad/25"],
}

function ProcessorForm({ processor, onDone }: { processor: Processor | null; onDone: () => void }) {
  const create = useCreateProcessor()
  const update = useUpdateProcessor(processor?.id ?? "")
  const [form, setForm] = useState<ProcessorInput>({
    name: processor?.name ?? "",
    service: processor?.service ?? null,
    country: processor?.country ?? null,
    data_categories: processor?.data_categories ?? [],
    dpa_signed: processor?.dpa_signed ?? false,
    dpa_date: processor?.dpa_date ?? null,
    security_review_on: processor?.security_review_on ?? null,
    security_result: processor?.security_result ?? null,
    risk_level: processor?.risk_level ?? 3,
    status: processor?.status ?? "active",
  })
  const set = <K extends keyof ProcessorInput>(k: K, v: ProcessorInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const error = create.error ?? update.error

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const body = { ...form, name: form.name.trim() }
    if (processor) update.mutate(body, { onSuccess: onDone })
    else create.mutate(body, { onSuccess: onDone })
  }

  const title = processor ? `Edit ${processor.name}` : "Add processor"
  return (
    <div role="dialog" aria-label={title} className="rise m-4 rounded-2xl border border-line bg-surface p-5">
      <h2 className="mb-3 text-[15px] font-semibold">{title}</h2>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-3">
        <label className={LABEL}>
          Name
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={200} className={FIELD} />
        </label>
        <label className={LABEL}>
          Service
          <input value={form.service ?? ""} onChange={(e) => set("service", e.target.value || null)} maxLength={300} className={FIELD} />
        </label>
        <label className={LABEL}>
          Country
          <input value={form.country ?? ""} onChange={(e) => set("country", e.target.value || null)} maxLength={100} className={FIELD} />
        </label>
        <fieldset className="grid gap-2 md:col-span-3">
          <legend className="mb-1 text-[12.5px] font-medium text-fg-2">Personal data they handle</legend>
          <div className="flex flex-wrap gap-2">
            {Object.entries(PII_CATEGORIES).map(([code, label]) => (
              <label key={code} className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[12.5px]">
                <input
                  type="checkbox"
                  checked={(form.data_categories ?? []).includes(code)}
                  onChange={(e) =>
                    set("data_categories", e.target.checked ? [...(form.data_categories ?? []), code] : (form.data_categories ?? []).filter((c) => c !== code))
                  }
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex items-center gap-2 text-[13px]">
          <input type="checkbox" checked={!!form.dpa_signed} onChange={(e) => set("dpa_signed", e.target.checked)} />
          Data processing agreement signed
        </label>
        <label className={LABEL}>
          Agreement date
          <input type="date" value={form.dpa_date ?? ""} onChange={(e) => set("dpa_date", e.target.value || null)} className={FIELD} />
        </label>
        <label className={LABEL}>
          Risk level
          <select value={form.risk_level} onChange={(e) => set("risk_level", Number(e.target.value))} className={FIELD}>
            {["Very low", "Low", "Medium", "High", "Very high"].map((w, i) => <option key={w} value={i + 1}>{w}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Last security review
          <input type="date" value={form.security_review_on ?? ""} onChange={(e) => set("security_review_on", e.target.value || null)} className={FIELD} />
        </label>
        <label className={LABEL}>
          Review result
          <select value={form.security_result ?? ""} onChange={(e) => set("security_result", (e.target.value || null) as Processor["security_result"])} className={FIELD}>
            <option value="">Not reviewed</option>
            {Object.entries(RESULT).map(([k, [v]]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className={LABEL}>
          Status
          <select value={form.status} onChange={(e) => set("status", e.target.value as Processor["status"])} className={FIELD}>
            <option value="active">Active</option>
            <option value="ended">Ended</option>
          </select>
        </label>
        <div className="flex items-center gap-2 md:col-span-3">
          <Button type="submit" size="sm" disabled={!form.name.trim() || create.isPending || update.isPending}>Save processor</Button>
          <Button type="button" size="sm" variant="secondary" onClick={onDone}>Cancel</Button>
          {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
        </div>
      </form>
    </div>
  )
}

export function Processors({ canManage }: { canManage: boolean }) {
  const processors = useProcessors()
  const [editing, setEditing] = useState<Processor | "new" | null>(null)
  const rows = processors.data ?? []
  return (
    <div>
      {canManage && !editing && (
        <div className="flex justify-end px-4 pt-3">
          <Button size="sm" onClick={() => setEditing("new")}>Add processor</Button>
        </div>
      )}
      {editing && <ProcessorForm processor={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      {processors.isSuccess && rows.length === 0 && (
        <p className="p-8 text-center text-fg-3">No processors yet. Add the vendors that handle personal data for you.</p>
      )}
      {rows.length > 0 && (
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["Processor", "Personal data", "Agreement", "Security review", "Risk", "Used by", ""].map((h) => (
                <th key={h} className="px-4 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className={`border-t border-line align-top hover:bg-subtle ${p.status === "ended" ? "opacity-60" : ""}`}>
                <td className="min-w-44 px-4 py-2.5">
                  <span className="font-medium">{p.name}</span>
                  <span className="block text-[12px] text-fg-3">{[p.service, p.country].filter(Boolean).join(" · ")}</span>
                </td>
                <td className="px-4 py-2.5"><CategoryChips codes={p.data_categories} /></td>
                <td className="px-4 py-2.5">
                  {p.dpa_signed ? (
                    <Tag tone="bg-ok-soft text-ok border-ok/25">Signed{p.dpa_date ? ` ${formatDate(p.dpa_date)}` : ""}</Tag>
                  ) : (
                    <Tag tone="bg-bad-soft text-bad border-bad/25">No agreement</Tag>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {p.security_result ? <Tag tone={RESULT[p.security_result][1]}>{RESULT[p.security_result][0]}</Tag> : <span className="text-fg-3">Not reviewed</span>}
                </td>
                <td className="px-4 py-2.5"><LevelBadge level={p.risk_level} /></td>
                <td className="px-4 py-2.5 text-[12.5px] text-fg-2">{p.activities.map((a) => a.code).join(", ") || "—"}</td>
                <td className="px-4 py-2.5 text-right">
                  {p.can_edit && (
                    <Button size="sm" variant="ghost" aria-label={`Edit ${p.name}`} onClick={() => setEditing(p)}>Edit</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
