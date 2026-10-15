import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useControls } from "../api/controls"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"

const THEMES = ["Organizational", "People", "Physical", "Technological"]

export function ControlsPage() {
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
    <div className="mx-auto grid max-w-6xl gap-4">
      <header>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022 · Annex A</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Controls</h1>
      </header>
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
    </div>
  )
}
