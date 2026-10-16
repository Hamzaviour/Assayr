import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { type FormEvent, useMemo, useState } from "react"
import { useControls } from "../api/controls"
import { useNiaControls } from "../api/nia"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"

const THEMES = ["Organizational", "People", "Physical", "Technological"]

function FrameworkSwitch({ nia }: { nia: boolean }) {
  const navigate = useNavigate({ from: "/controls" })
  const options = [
    { label: "ISO/IEC 27001", active: !nia, search: {} },
    { label: "NIA v2.1", active: nia, search: { framework: "nia" as const } },
  ]
  return (
    <div role="radiogroup" aria-label="Framework" className="inline-flex rounded-lg border border-line bg-surface p-0.5">
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
  const nia = search.framework === "nia"
  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">
            {nia ? "Qatar National Information Assurance Standard v2.1" : "ISO/IEC 27001:2022 · Annex A"}
          </p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Controls</h1>
        </div>
        <FrameworkSwitch nia={nia} />
      </header>
      {nia ? <NiaControls domain={search.domain} /> : <IsoControls />}
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
  const term = filter.trim().toLowerCase()
  const rows = all.filter(
    (c) => (!domain || c.domain === domain) && (!term || c.ref.toLowerCase().includes(term) || c.title.toLowerCase().includes(term)),
  )
  return (
    <section className="rounded-xl border border-line bg-surface">
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
                  {c.mapped.length === 0 ? (
                    <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium">NIA only</span>
                  ) : (
                    c.mapped.map((m) => m.code).join(", ")
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

function IsoControls() {
  const search = useSearch({ from: "/app/controls" })
  const navigate = useNavigate({ from: "/controls" })
  const [query, setQuery] = useState(search.q ?? "")
  const controls = useControls({ theme: search.theme, q: search.q, owner: search.owner })
  const rows = controls.data?.pages.flatMap((p) => p.items) ?? []

  function onSearch(event: FormEvent) {
    event.preventDefault()
    navigate({ search: (prev) => ({ ...prev, q: query.trim() || undefined }) })
  }

  return (
      <section className="rounded-xl border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3.5 py-3">
          <label htmlFor="theme-filter" className="text-[13px] text-fg-2">Theme</label>
          <select
            id="theme-filter"
            value={search.theme ?? ""}
            onChange={(e) => navigate({ search: (prev) => ({ ...prev, theme: e.target.value || undefined }) })}
            className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
          >
            <option value="">All themes</option>
            {THEMES.map((t) => <option key={t} value={t}>{t}</option>)}
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
                  <td className="px-3.5 py-2.5"><ControlId code={c.code} /></td>
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
