import { Link } from "@tanstack/react-router"
import { useDashboard } from "../api/dashboard"
import { ProgressBar } from "../components/charts"

const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value)}%`)

export function CompliancePage() {
  const dashboard = useDashboard()
  const frameworks = dashboard.data?.frameworks ?? []
  return (
    <div className="mx-auto grid max-w-5xl gap-6">
      <header>
        <p className="mb-1 text-[13px] text-fg-3">Frameworks you are working towards</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Compliance</h1>
      </header>
      {dashboard.isError && <p role="alert">{dashboard.error.message}</p>}
      {dashboard.isPending && <div className="h-40 animate-pulse rounded-xl bg-subtle" aria-label="Loading" />}
      {frameworks.map((f) => (
        <article key={f.code} className="grid gap-5 rounded-xl border border-line bg-surface p-6">
          <p className="flex items-baseline justify-between gap-3">
            <span className="text-[19px]">
              <strong>{f.name}</strong> <span className="text-fg-3">{f.version}</span>
            </span>
            <span className="font-display text-[30px] font-extrabold leading-none tabular-nums">{percent(f.readiness)}</span>
          </p>
          <ProgressBar value={f.compliant} max={f.total} label={`${f.name} controls compliant`} />
          <p className="text-[13px] text-fg-2">
            {f.compliant} controls compliant · {f.total} total
            {f.excluded > 0 && <span className="text-fg-3"> · {f.excluded} excluded in the SoA</span>}
          </p>
          {f.groups.length > 0 && (
            <div className="border-t border-line pt-4">
              <h2 className="mb-2 text-[14px] font-semibold">Annex A themes</h2>
              <ul className="grid gap-1">
                {f.groups.map((g) => (
                  <li key={g.name}>
                    <Link
                      to="/controls"
                      search={{ theme: g.name }}
                      className="grid grid-cols-[minmax(0,150px)_minmax(0,1fr)_minmax(0,130px)] items-center gap-4 rounded-lg px-2 py-2.5 hover:bg-subtle"
                    >
                      <span className="text-[14px] font-medium">{g.name}</span>
                      <ProgressBar value={g.compliant} max={g.total} label={`${g.name} controls compliant`} />
                      <span className="text-right text-[13px] tabular-nums text-fg-2">
                        {g.compliant} of {g.total} compliant
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </article>
      ))}
    </div>
  )
}
