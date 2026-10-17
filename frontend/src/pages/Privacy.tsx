import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { type CSSProperties, type FormEvent, useState } from "react"
import {
  ACTIVITY_STATUS,
  type Activity,
  LAWFUL_BASIS,
  privacyExportUrl,
  useActivities,
  useCreateActivity,
  useInventory,
  usePrivacySummary,
} from "../api/privacy"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { LevelBadge } from "../components/LevelBadge"
import { formatDate } from "../lib/format"
import { PII_CATEGORIES, PII_VOLUME, SENSITIVE } from "../lib/privacy"
import { Breaches } from "./privacy/Breaches"
import { Overview, type PrivacyTab } from "./privacy/Overview"
import { PdpplTab } from "./privacy/PdpplTab"
import { Processors } from "./privacy/Processors"
import { Requests } from "./privacy/Requests"

const order = (i: number) => ({ "--i": i }) as CSSProperties
const FIELD = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"

export const STATUS_TONE: Record<string, string> = {
  draft: "bg-transparent text-fg-2 border-line-2 border-dashed",
  active: "bg-ok-soft text-ok border-ok/25",
  retired: "bg-subtle text-fg-3 border-line",
}

export function Tag({ tone, children }: { tone: string; children: React.ReactNode }) {
  return <span className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${tone}`}>{children}</span>
}

export function CategoryChips({ codes }: { codes: string[] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {codes.map((c) => (
        <span
          key={c}
          className={`rounded-full px-2 py-0.5 text-[11.5px] font-medium ${SENSITIVE.has(c) ? "bg-bad-soft text-bad" : "bg-primary-soft text-primary"}`}
        >
          {PII_CATEGORIES[c] ?? c}
        </span>
      ))}
    </span>
  )
}

function Summary() {
  const summary = usePrivacySummary()
  const s = summary.data
  const items: [string, number | undefined, string][] = [
    ["PII assets", s?.pii_assets, "text-primary"],
    ["Sensitive assets", s?.sensitive_assets, "text-bad"],
    ["Processing activities", s?.activities, "text-fg"],
    ["Active", s?.active_activities, "text-ok"],
    ["Cross-border transfers", s?.cross_border, "text-warn"],
    ["Reviews due", s?.reviews_due, s?.reviews_due ? "text-bad" : "text-fg-3"],
  ]
  return (
    <ul aria-label="Privacy at a glance" className="grid grid-cols-2 gap-3 md:grid-cols-6">
      {items.map(([label, value, tone], i) => (
        <li key={label} className="lift rise relative overflow-hidden rounded-2xl border border-line bg-surface p-4" style={order(i + 1)}>
          <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
          <p className="text-[12px] text-fg-3">{label}</p>
          <p className={`font-display text-[28px] font-extrabold leading-tight tabular-nums ${tone}`}>{value ?? "—"}</p>
        </li>
      ))}
    </ul>
  )
}

function NewActivity({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateActivity()
  const [name, setName] = useState("")
  const [basis, setBasis] = useState("contract")
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      {
        name: name.trim(),
        purpose: null,
        data_subjects: [],
        data_categories: [],
        lawful_basis: basis,
        recipients: null,
        cross_border: false,
        transfer_countries: null,
        retention: null,
        security_measures: null,
        owner_id: null,
        status: "draft",
        review_due: null,
      },
      { onSuccess: (a) => navigate({ to: "/privacy/$id", params: { id: a.id } }) },
    )
  }
  return (
    <div role="dialog" aria-label="New processing activity" className="rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <h2 className="mb-3 text-[15px] font-semibold">New processing activity</h2>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-end">
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Payroll" required maxLength={200} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Lawful basis
          <select value={basis} onChange={(e) => setBasis(e.target.value)} className={FIELD}>
            {Object.entries(LAWFUL_BASIS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={!name.trim() || create.isPending}>Create activity</Button>
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
      {create.isError && <p role="alert" className="mt-2 text-[13px] text-bad">{create.error.message}</p>}
    </div>
  )
}

function Activities({ rows }: { rows: Activity[] }) {
  if (rows.length === 0) {
    return <p className="p-8 text-center text-fg-3">No processing activities yet. Record what personal data you process and why.</p>
  }
  return (
    <table className="w-full text-[13.5px]">
      <thead>
        <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
          {["Code", "Activity", "Lawful basis", "Personal data", "Flags", "Stored on", "Status", "Next review"].map((h) => (
            <th key={h} className="px-4 py-3 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((a) => (
          <tr key={a.id} className="border-t border-line align-top hover:bg-subtle">
            <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12.5px] text-fg-3">{a.code}</td>
            <td className="min-w-48 px-4 py-2.5">
              <Link to="/privacy/$id" params={{ id: a.id }} className="font-medium hover:text-primary">{a.name}</Link>
            </td>
            <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{LAWFUL_BASIS[a.lawful_basis] ?? a.lawful_basis}</td>
            <td className="px-4 py-2.5"><CategoryChips codes={a.data_categories} /></td>
            <td className="px-4 py-2.5">
              <span className="flex flex-wrap gap-1">
                {a.sensitive && <Tag tone="bg-bad-soft text-bad border-bad/25">Sensitive</Tag>}
                {a.cross_border && <Tag tone="bg-warn-soft text-warn border-warn/25">Cross-border</Tag>}
                {a.review_overdue && <Tag tone="bg-bad text-white border-bad">Review due</Tag>}
              </span>
            </td>
            <td className="px-4 py-2.5 tabular-nums text-fg-2">{a.assets.length}</td>
            <td className="px-4 py-2.5"><Tag tone={STATUS_TONE[a.status]}>{ACTIVITY_STATUS[a.status] ?? a.status}</Tag></td>
            <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{a.review_due ? formatDate(a.review_due) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Inventory() {
  const inventory = useInventory()
  const rows = inventory.data ?? []
  if (inventory.isSuccess && rows.length === 0) {
    return <p className="p-8 text-center text-fg-3">No asset is marked as holding personal data yet. Mark them on the Assets page.</p>
  }
  return (
    <table className="w-full text-[13.5px]">
      <thead>
        <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
          {["Asset", "Personal data", "People", "Criticality", "Owner", "Activities"].map((h) => (
            <th key={h} className="px-4 py-3 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-t border-line align-top hover:bg-subtle">
            <td className="min-w-48 px-4 py-2.5">
              <span className="font-mono text-[12px] text-fg-3">{r.code}</span> <span className="font-medium">{r.name}</span>
              {r.pii_sensitive && <span className="ml-2"><Tag tone="bg-bad-soft text-bad border-bad/25">Sensitive</Tag></span>}
            </td>
            <td className="px-4 py-2.5"><CategoryChips codes={r.pii_categories} /></td>
            <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{r.pii_volume ? PII_VOLUME[r.pii_volume] : "—"}</td>
            <td className="px-4 py-2.5"><LevelBadge level={r.criticality} /></td>
            <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{r.owner?.full_name ?? "Unassigned"}</td>
            <td className="px-4 py-2.5 text-[12.5px] text-fg-2">
              {r.activities.length ? r.activities.map((a) => `${a.code} ${a.name}`).join(", ") : <span className="text-warn">Not in any activity</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const TABS: { key: PrivacyTab; label: string; sensitive?: boolean }[] = [
  { key: "overview", label: "Overview" },
  { key: "activities", label: "Processing activities" },
  { key: "inventory", label: "PII inventory" },
  { key: "requests", label: "Requests", sensitive: true },
  { key: "breaches", label: "Breaches", sensitive: true },
  { key: "processors", label: "Processors" },
  { key: "pdppl", label: "PDPPL" },
]

export function PrivacyPage() {
  const me = useMe()
  const navigate = useNavigate({ from: "/privacy" })
  const { tab = "overview" } = useSearch({ from: "/app/privacy" })
  const activities = useActivities()
  const [creating, setCreating] = useState(false)
  const perms = me.data?.permissions ?? []
  const canManage = perms.includes("privacy:manage")
  const sensitive = perms.includes("privacy:sensitive")
  const tabs = TABS.filter((t) => !t.sensitive || sensitive)
  const current = tabs.some((t) => t.key === tab) ? tab : "overview"
  const go = (next: PrivacyTab) => navigate({ search: { tab: next === "overview" ? undefined : next } })

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="rise flex flex-wrap items-end justify-between gap-3" style={order(0)}>
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Privacy · Qatar PDPPL · ISO 27001 A.5.34</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Data privacy</h1>
          <p className="mt-1 text-[13px] text-fg-2">What personal data you process, why, on what basis, where it is kept and for how long.</p>
        </div>
        <div className="flex gap-2">
          <a href={privacyExportUrl} className="inline-flex items-center rounded-lg border border-line px-3 py-2 text-[13px] font-semibold text-primary hover:bg-subtle">
            Export Excel
          </a>
          {canManage && !creating && <Button onClick={() => setCreating(true)}>New activity</Button>}
        </div>
      </header>
      <Summary />
      {creating && <NewActivity onClose={() => setCreating(false)} />}
      <section className="rounded-xl border border-line bg-surface">
        <div role="tablist" aria-label="Data privacy views" className="flex flex-wrap gap-1 border-b border-line px-3 pt-2">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={current === key}
              onClick={() => go(key)}
              className={`-mb-px border-b-2 px-3 py-2 text-[13.5px] font-semibold transition-colors ${
                current === key ? "border-primary text-primary" : "border-transparent text-fg-2 hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="overflow-x-auto">
          {activities.isError && <p role="alert" className="p-4">{activities.error.message}</p>}
          {current === "overview" && <Overview go={go} sensitive={sensitive} />}
          {current === "activities" && activities.isSuccess && <Activities rows={activities.data} />}
          {current === "inventory" && <Inventory />}
          {current === "requests" && <Requests canManage={canManage} />}
          {current === "breaches" && <Breaches canManage={canManage} />}
          {current === "processors" && <Processors canManage={canManage} />}
          {current === "pdppl" && <PdpplTab />}
        </div>
      </section>
    </div>
  )
}
