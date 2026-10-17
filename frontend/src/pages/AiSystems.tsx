import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { type AiSystemInput, SOURCE_LABEL, useAiSystems, useCreateAiSystem } from "../api/ai"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { LEVEL_LABEL, LevelBadge } from "../components/LevelBadge"
import { Status } from "../components/Status"
import { StatusBar } from "../components/StatusBar"
import { countBy, statusSegments } from "../lib/statusBars"

export const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
export const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
export const LIFECYCLE_LABEL: Record<string, string> = {
  planned: "Planned",
  development: "Development",
  validation: "Validation",
  deployed: "Deployed",
  retired: "Retired",
}

function NewSystem({ onClose }: { onClose: () => void }) {
  const create = useCreateAiSystem()
  const [form, setForm] = useState<Required<Pick<AiSystemInput, "name" | "purpose" | "source" | "lifecycle" | "risk_level">> & { provider: string; model_type: string }>({
    name: "",
    purpose: "",
    source: "in_house",
    lifecycle: "planned",
    risk_level: 3,
    provider: "",
    model_type: "",
  })
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      {
        ...form,
        name: form.name.trim(),
        purpose: form.purpose?.trim() || null,
        provider: form.provider.trim() || null,
        model_type: form.model_type.trim() || null,
      },
      { onSuccess: onClose },
    )
  }
  return (
    <form aria-label="Register an AI system" onSubmit={onSubmit} className="rise grid gap-3 rounded-xl border border-line bg-surface p-5 md:grid-cols-3">
      <label className={LABEL}>
        Name
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength={200} className={FIELD} />
      </label>
      <label className={`${LABEL} md:col-span-2`}>
        Purpose
        <input value={form.purpose ?? ""} onChange={(e) => setForm({ ...form, purpose: e.target.value })} maxLength={5000} className={FIELD} />
      </label>
      <label className={LABEL}>
        Source
        <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value as AiSystemInput["source"] & string })} className={FIELD}>
          {Object.entries(SOURCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label className={LABEL}>
        Provider
        <input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} maxLength={200} className={FIELD} />
      </label>
      <label className={LABEL}>
        Model type
        <input value={form.model_type} onChange={(e) => setForm({ ...form, model_type: e.target.value })} maxLength={100} placeholder="e.g. classification, LLM" className={FIELD} />
      </label>
      <label className={LABEL}>
        Lifecycle
        <select value={form.lifecycle} onChange={(e) => setForm({ ...form, lifecycle: e.target.value as AiSystemInput["lifecycle"] & string })} className={FIELD}>
          {Object.entries(LIFECYCLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label className={LABEL}>
        Risk level
        <select value={form.risk_level} onChange={(e) => setForm({ ...form, risk_level: Number(e.target.value) })} className={FIELD}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{LEVEL_LABEL[n]}</option>)}
        </select>
      </label>
      <div className="flex items-center gap-2 md:col-span-3">
        <Button type="submit" size="sm" disabled={!form.name.trim() || create.isPending}>Register</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
        {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
      </div>
    </form>
  )
}

export function AiSystemsPage() {
  const systems = useAiSystems()
  const me = useMe()
  const canManage = (me.data?.permissions ?? []).includes("ai:manage")
  const [creating, setCreating] = useState(false)
  const [lifecycle, setLifecycle] = useState<string | null>(null)
  const all = systems.data ?? []
  const rows = lifecycle ? all.filter((s) => s.lifecycle === lifecycle) : all
  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 42001 · AI management system</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">AI systems</h1>
        </div>
        {canManage && !creating && <Button onClick={() => setCreating(true)}>Register AI system</Button>}
      </header>
      {creating && <NewSystem onClose={() => setCreating(false)} />}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        {all.length > 0 && (
          <div className="border-b border-line px-4 py-3">
            <StatusBar label="AI systems by lifecycle" selected={lifecycle} onSelect={setLifecycle}
              segments={statusSegments("aiLifecycle", countBy(all, (s) => s.lifecycle))} />
          </div>
        )}
        {systems.isError && <p role="alert" className="p-4">{systems.error.message}</p>}
        {systems.isPending && <p role="status" className="p-4 text-fg-3">Loading…</p>}
        {systems.isSuccess && all.length === 0 && (
          <p className="p-8 text-center text-fg-3">No AI systems yet. Register the AI you build, buy or use so you can assess its impact.</p>
        )}
        {rows.length > 0 && (
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
                {["System", "Name", "Source", "Lifecycle", "Risk", "Impact assessment", "Owner"].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} className={`border-t border-line hover:bg-subtle ${s.status === "retired" ? "opacity-60" : ""}`}>
                  <td className="px-4 py-2.5 font-mono text-[12.5px] font-semibold text-primary">{s.code}</td>
                  <td className="min-w-48 px-4 py-2.5">
                    <Link to="/ai/$id" params={{ id: s.id }} className="text-fg hover:text-primary">{s.name}</Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{SOURCE_LABEL[s.source]}</td>
                  <td className="px-4 py-2.5"><Status area="aiLifecycle" value={s.lifecycle} /></td>
                  <td className="px-4 py-2.5"><LevelBadge level={s.risk_level} /></td>
                  <td className="px-4 py-2.5">
                    {s.assessment_status ? <Status area="aiia" value={s.assessment_status} /> : <span className="text-[12.5px] text-fg-3">Not started</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{s.owner?.full_name ?? "Unassigned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
