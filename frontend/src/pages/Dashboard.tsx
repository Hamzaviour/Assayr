import { useControlStats } from "../api/controls"
import { useMe } from "../auth/session"
import { StatusPill } from "../components/StatusPill"

export function DashboardPage() {
  const me = useMe()
  const stats = useControlStats()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <header className="mb-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Welcome, {firstName}</h1>
      </header>
      {stats.isError && <p role="alert">{stats.error.message}</p>}
      {stats.data && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <section className="grid content-start gap-3 rounded-xl border border-line bg-surface p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Controls in scope</p>
            <p className="font-display text-4xl font-extrabold tabular-nums tracking-tight">{stats.data.total}</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.data.by_status).map(([status, n]) => (
                <span key={status} className="inline-flex items-center gap-1.5 text-[13px]">
                  <StatusPill status={status} /> <b className="tabular-nums">{n}</b>
                </span>
              ))}
            </div>
            <p className="text-[13px] text-fg-2">
              Readiness appears once the first evidence is verified. Start by describing how each control is
              implemented.
            </p>
          </section>
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">By Annex A theme</h2>
            <table className="w-full text-[13.5px]">
              <tbody>
                {Object.entries(stats.data.by_theme).map(([theme, n]) => (
                  <tr key={theme} className="border-b border-line last:border-0">
                    <td className="px-5 py-2.5">{theme}</td>
                    <td className="px-5 py-2.5 text-right font-medium tabular-nums">{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  )
}
