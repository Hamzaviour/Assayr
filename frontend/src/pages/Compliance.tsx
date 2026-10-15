import { Link } from "@tanstack/react-router"
import { useDashboard } from "../api/dashboard"
import { useReadiness } from "../api/evidence"
import { ProgressBar } from "../components/charts"

const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value)}%`)

export function CompliancePage() {
  const dashboard = useDashboard()
  const readiness = useReadiness()
  const frameworks = dashboard.data?.frameworks ?? []
  const themes = Object.entries(readiness.data?.by_theme ?? {})
  return (
    <div className="mx-auto grid max-w-5xl gap-6">
      <header>
        <p className="mb-1 text-[13px] text-fg-3">Frameworks you are working towards</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Compliance</h1>
      </header>
      {(dashboard.isError || readiness.isError) && (
        <p role="alert">{(dashboard.error ?? readiness.error)?.message}</p>
      )}
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
          </p>
          {themes.length > 0 && (
            <div className="border-t border-line pt-4">
              <h2 className="mb-2 text-[14px] font-semibold">Annex A themes</h2>
              <ul className="grid gap-1">
                {themes.map(([theme, value]) => (
                  <li key={theme}>
                    <Link
                      to="/controls"
                      search={{ theme }}
                      className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)_52px] items-center gap-4 rounded-lg px-2 py-2.5 hover:bg-subtle"
                    >
                      <span className="text-[14px] font-medium">{theme}</span>
                      <ProgressBar value={Math.round(value ?? 0)} max={100} label={`${theme} readiness`} />
                      <span className="text-right text-[13px] tabular-nums text-fg-2">{percent(value)}</span>
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
