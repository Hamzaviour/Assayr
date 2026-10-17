import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { type FormEvent, useMemo, useState } from "react"
import { type ControlFramework, useControlStats, useControls, useCreateActivity } from "../api/controls"
import type { ControlSummary } from "../api/types"
import { useMe } from "../auth/session"
import { useNiaControls } from "../api/nia"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"
import { StatusBar } from "../components/StatusBar"
import { countBy, statusSegments } from "../lib/statusBars"

const THEMES = ["Organizational", "People", "Physical", "Technological"]

type Framework = "nia" | "iso42001" | "soc2" | undefined
const SUBTITLE: Record<string, string> = {
  iso27001: "ISO/IEC 27001:2022 · Annex A",
  nia: "Qatar National Information Assurance Standard v2.1",
  iso42001: "ISO/IEC 42001:2023 · AI management system",
  soc2: "SOC 2 · Trust Services Criteria, Security",
}

function FrameworkSwitch({ framework }: { framework: Framework }) {
  const navigate = useNavigate({ from: "/controls" })
  const options = [
    { label: "ISO/IEC 27001", active: !framework, search: {} },
    { label: "NIA v2.1", active: framework === "nia", search: { framework: "nia" as const } },
    { label: "ISO/IEC 42001", active: framework === "iso42001", search: { framework: "iso42001" as const } },
    { label: "SOC 2", active: framework === "soc2", search: { framework: "soc2" as const } },
  ]
  return (
    <div role="radiogroup" aria-label="Framework" className="inline-flex flex-wrap rounded-lg border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.label}
          type="button"
          role="radio"
          aria-checked={o.active}
          onClick={() => navigate({ search: o.search })}
          className={`rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors duration-200 ${
            o.active ? "bg-primary text-on-primary" : "text-fg-2 hover:bg-subtle"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function ControlsPage() {
  const search = useSearch({ from: "/app/controls" })
  const framework = search.framework
  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">
            {SUBTITLE[framework ?? "iso27001"]}
          </p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Controls</h1>
        </div>
        <FrameworkSwitch framework={framework} />
      </header>
      {framework === "nia" ? (
        <NiaControls domain={search.domain} />
      ) : framework === "soc2" ? (
        <Soc2Controls />
      ) : (
        <IsoControls key={framework ?? "iso27001"} framework={framework ?? "iso27001"} />
      )}
    </div>
  )
}

function NiaControls({ domain }: { domain?: string }) {
  const navigate = useNavigate({ from: "/controls" })
  const controls = useNiaControls()
  const [filter, setFilter] = useState("")
  const all = controls.data ?? []
  const domains = useMemo(() => {
    const seen = new Map<string, string>()
    for (const c of all) seen.set(c.domain, c.domain_name)
    return [...seen]
  }, [all])
  const [status, setStatus] = useState<string | null>(null)
  const term = filter.trim().toLowerCase()
  const inDomain = all.filter((c) => !domain || c.domain === domain)
  const rows = inDomain.filter(
    (c) => (!status || c.status === status) && (!term || c.ref.toLowerCase().includes(term) || c.title.toLowerCase().includes(term)),
  )
  return (
    <section className="rounded-xl border border-line bg-surface">
      {all.length > 0 && (
        <div className="border-b border-line px-3.5 py-3">
          <StatusBar
            label="NIA controls by status"
            selected={status}
            onSelect={setStatus}
            segments={statusSegments("control", countBy(inDomain, (c) => c.status))}
          />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3.5 py-3">
        <label htmlFor="domain-filter" className="text-[13px] text-fg-2">Domain</label>
        <select
          id="domain-filter"
          value={domain ?? ""}
          onChange={(e) => navigate({ search: (prev) => ({ ...prev, domain: e.target.value || undefined }) })}
          className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
        >
          <option value="">All domains</option>
          {domains.map(([code, name]) => (
            <option key={code} value={code}>{code} · {name}</option>
          ))}
        </select>
        <label htmlFor="nia-search" className="sr-only">Filter NIA controls</label>
        <input
          id="nia-search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by reference or title"
          className="ml-auto w-full min-w-0 max-w-72 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
        />
      </div>
      {controls.isError && <p role="alert" className="p-4">{controls.error.message}</p>}
      {controls.isPending && <p role="status" className="p-4 text-fg-3">Loading…</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              <th className="px-3.5 py-3 font-medium">Ref</th>
              <th className="px-3.5 py-3 font-medium">Control</th>
              <th className="px-3.5 py-3 font-medium">Domain</th>
              <th className="px-3.5 py-3 font-medium">Status</th>
              <th className="px-3.5 py-3 font-medium">Mapped ISO controls</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.ref} className={`border-t border-line hover:bg-subtle ${c.applicable ? "" : "opacity-60"}`}>
                <td className="px-3.5 py-2.5"><ControlId code={c.ref} /></td>
                <td className="min-w-60 px-3.5 py-2.5">
                  <Link to="/nia/$ref" params={{ ref: c.ref }} className="text-fg hover:text-primary">
                    {c.title}
                  </Link>
                  {c.mandatory && (
                    <span className="ml-2 rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-semibold text-primary">Mandatory</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{c.domain_name}</td>
                <td className="px-3.5 py-2.5">
                  {c.applicable ? <StatusPill status={c.status} /> : <span className="text-[12.5px] text-fg-3">Not applicable</span>}
                </td>
                <td className="px-3.5 py-2.5 text-[12.5px] text-fg-2">
                  {c.own_control ? (
                    <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium">NIA only</span>
                  ) : (
                    c.mapped.map((m) => m.code).join(", ") || "—"
                  )}
                </td>
              </tr>
            ))}
            {controls.isSuccess && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3.5 py-8 text-center text-fg-3">
                  {all.length === 0 ? "NIA is not set up in this installation yet." : "No NIA controls match these filters."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function IsoControls({ framework }: { framework: ControlFramework }) {
  const search = useSearch({ from: "/app/controls" })
  const navigate = useNavigate({ from: "/controls" })
  const [query, setQuery] = useState(search.q ?? "")
  const controls = useControls({ theme: search.theme, q: search.q, owner: search.owner, status: search.status, framework })
  const stats = useControlStats(framework)
  const themes = framework === "iso27001" ? THEMES : Object.keys(stats.data?.by_theme ?? {})
  const rows = controls.data?.pages.flatMap((p) => p.items) ?? []

  function onSearch(event: FormEvent) {
    event.preventDefault()
    navigate({ search: (prev) => ({ ...prev, q: query.trim() || undefined }) })
  }

  return (
      <section className="rounded-xl border border-line bg-surface">
        {stats.data && (
          <div className="border-b border-line px-3.5 py-3">
            <StatusBar
              label="Controls by status"
              selected={search.status ?? null}
              onSelect={(status) => navigate({ search: (prev) => ({ ...prev, status: status ?? undefined }) })}
              segments={statusSegments("control", stats.data.by_status)}
            />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3.5 py-3">
          <label htmlFor="theme-filter" className="text-[13px] text-fg-2">Theme</label>
          <select
            id="theme-filter"
            value={search.theme ?? ""}
            onChange={(e) => navigate({ search: (prev) => ({ ...prev, theme: e.target.value || undefined }) })}
            className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
          >
            <option value="">All themes</option>
            {themes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {search.owner === "none" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-2.5 py-1 text-[12.5px] text-primary">
              Unassigned only
              <button
                type="button"
                aria-label="Show all owners"
                onClick={() => navigate({ search: (prev) => ({ ...prev, owner: undefined }) })}
                className="rounded-full px-1 hover:bg-surface"
              >
                ×
              </button>
            </span>
          )}
          <form onSubmit={onSearch} className="ml-auto flex min-w-0 flex-1 justify-end gap-2" role="search">
            <label htmlFor="control-search" className="sr-only">Search controls</label>
            <input
              id="control-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by ID or title"
              className="w-full min-w-0 max-w-72 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
            />
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
        </div>
        {controls.isError && <p role="alert" className="p-4">{controls.error.message}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
                <th className="px-3.5 py-3 font-medium">ID</th>
                <th className="px-3.5 py-3 font-medium">Control</th>
                <th className="px-3.5 py-3 font-medium">Status</th>
                <th className="px-3.5 py-3 font-medium">Score</th>
                <th className="px-3.5 py-3 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-t border-line hover:bg-subtle">
                  <td className="px-3.5 py-2.5"><ControlId code={c.ref ?? c.code} /></td>
                  <td className="min-w-60 px-3.5 py-2.5">
                    <Link to="/controls/$code" params={{ code: c.code }} className="text-fg hover:text-primary">
                      {c.title}
                    </Link>
                  </td>
                  <td className="px-3.5 py-2.5"><StatusPill status={c.status} /></td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">{c.score === null ? "—" : `${Math.round(c.score)}%`}</td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{c.owner?.full_name ?? "Unassigned"}</td>
                </tr>
              ))}
              {controls.isSuccess && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3.5 py-8 text-center text-fg-3">No controls match these filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {controls.hasNextPage && (
          <div className="border-t border-line p-3 text-center">
            <Button variant="secondary" onClick={() => controls.fetchNextPage()} disabled={controls.isFetchingNextPage}>
              {controls.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </section>
  )
}

const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"

function NewActivity({ onClose }: { onClose: () => void }) {
  const create = useCreateActivity()
  const [form, setForm] = useState({ code: "", title: "", test_procedure: "" })
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      { code: form.code.trim(), title: form.title.trim(), test_procedure: form.test_procedure.trim() || null },
      { onSuccess: onClose },
    )
  }
  return (
    <form onSubmit={onSubmit} aria-label="Add a SOC 2 control activity" className="rise grid gap-3 border-b border-line p-4 md:grid-cols-[160px_minmax(0,1fr)]">
      <label className={LABEL}>
        Control number
        <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required maxLength={20} placeholder="CC6.1.2" className={FIELD} />
      </label>
      <label className={LABEL}>
        Control
        <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={300} className={FIELD} />
      </label>
      <label className={`${LABEL} md:col-span-2`}>
        Detailed test of controls
        <textarea value={form.test_procedure} onChange={(e) => setForm({ ...form, test_procedure: e.target.value })} rows={2} maxLength={5000} className={FIELD} />
      </label>
      <div className="flex items-center gap-2 md:col-span-2">
        <Button type="submit" size="sm" disabled={!form.code.trim() || !form.title.trim() || create.isPending}>Add</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
        {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
      </div>
    </form>
  )
}

function Soc2Controls() {
  const controls = useControls({ framework: "soc2", limit: 200 })
  const me = useMe()
  const canWrite = (me.data?.permissions ?? []).includes("controls:write")
  const all = controls.data?.pages.flatMap((p) => p.items) ?? []
  const criteria = all.filter((c) => c.code.split(".").length === 2)
  const activities = (code: string) => all.filter((c) => c.code.startsWith(`${code}.`))
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const [adding, setAdding] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const shown = status ? criteria.filter((c) => c.status === status) : criteria
  return (
    <section className="rounded-xl border border-line bg-surface">
      {criteria.length > 0 && (
        <div className="border-b border-line px-3.5 py-3">
          <StatusBar
            label="SOC 2 criteria by status"
            selected={status}
            onSelect={setStatus}
            segments={statusSegments("control", countBy(criteria, (c) => c.status))}
          />
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3.5 py-3">
        <p className="text-[13px] text-fg-2">
          {criteria.length} criteria · {all.length - criteria.length} control activities
        </p>
        {canWrite && !adding && <Button size="sm" onClick={() => setAdding(true)}>Add activity</Button>}
      </div>
      {adding && <NewActivity onClose={() => setAdding(false)} />}
      {controls.isError && <p role="alert" className="p-4">{controls.error.message}</p>}
      {controls.isPending && <p role="status" className="p-4 text-fg-3">Loading…</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              <th className="px-3.5 py-3 font-medium">Criterion</th>
              <th className="px-3.5 py-3 font-medium">Control</th>
              <th className="px-3.5 py-3 font-medium">Series</th>
              <th className="px-3.5 py-3 font-medium">Status</th>
              <th className="px-3.5 py-3 font-medium">Activities</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => {
              const kids = activities(c.code)
              return (
                <Soc2Rows key={c.id} criterion={c} kids={kids} open={!!open[c.code]} onToggle={() => setOpen({ ...open, [c.code]: !open[c.code] })} />
              )
            })}
            {controls.isSuccess && shown.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3.5 py-8 text-center text-fg-3">
                  {criteria.length === 0 ? "SOC 2 is not set up in this installation yet." : "No criteria match this filter."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Soc2Rows({ criterion: c, kids, open, onToggle }: { criterion: ControlSummary; kids: ControlSummary[]; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="border-t border-line hover:bg-subtle">
        <td className="px-3.5 py-2.5"><ControlId code={c.code} /></td>
        <td className="min-w-60 px-3.5 py-2.5">
          <Link to="/controls/$code" params={{ code: c.code }} className="text-fg hover:text-primary">{c.title}</Link>
        </td>
        <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{c.theme}</td>
        <td className="px-3.5 py-2.5"><StatusPill status={c.status} /></td>
        <td className="whitespace-nowrap px-3.5 py-2.5">
          {kids.length === 0 ? (
            <span className="text-[12.5px] text-fg-3">None yet</span>
          ) : (
            <button
              type="button"
              aria-expanded={open}
              aria-label={`${open ? "Hide" : "Show"} activities for ${c.code}`}
              onClick={onToggle}
              className="rounded-md px-1.5 py-0.5 text-[12.5px] font-semibold text-primary hover:bg-primary-soft"
            >
              <span>{`${kids.length} ${kids.length === 1 ? "activity" : "activities"}`}</span>{" "}
              <span aria-hidden="true">{open ? "▴" : "▾"}</span>
            </button>
          )}
        </td>
      </tr>
      {open &&
        kids.map((a) => (
          <tr key={a.id} className="border-t border-line bg-subtle/50">
            <td className="py-2 pl-8 pr-3.5"><ControlId code={a.code} /></td>
            <td className="min-w-60 px-3.5 py-2" colSpan={2}>
              <Link to="/controls/$code" params={{ code: a.code }} className="text-fg hover:text-primary">{a.title}</Link>
            </td>
            <td className="px-3.5 py-2"><StatusPill status={a.status} /></td>
            <td className="px-3.5 py-2 text-[12.5px] text-fg-2">{a.owner?.full_name ?? "Unassigned"}</td>
          </tr>
        ))}
    </>
  )
}

