import { useReadiness } from "../api/evidence"
import { useMe } from "../auth/session"
import { ReadinessRing } from "../components/ReadinessRing"
import { StatusPill } from "../components/StatusPill"

const ORDER = ["compliant", "at_risk", "in_review", "in_progress", "non_compliant", "not_started", "excluded"]

export function DashboardPage() {
  const me = useMe()
  const readiness = useReadiness()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""
  const data = readiness.data

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <header className="mb-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Welcome, {firstName}</h1>
      </header>
      {readiness.isError && <p role="alert">{readiness.error.message}</p>}
      {data && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <section className="grid content-start gap-4 rounded-xl border border-line bg-surface p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Readiness</p>
            {data.readiness === null ? (
              <p className="text-[13px] text-fg-2">
                Readiness appears once the first evidence is verified. Open a control and upload its evidence to
                start.
              </p>
            ) : (
              <ReadinessRing value={data.readiness} />
            )}
            <div className="flex flex-wrap gap-2">
              {ORDER.filter((s) => data.status_counts[s]).map((status) => (
                <span key={status} className="inline-flex items-center gap-1.5 text-[13px]">
                  <StatusPill status={status} /> <b className="tabular-nums">{data.status_counts[status]}</b>
                </span>
              ))}
            </div>
          </section>
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Readiness by Annex A theme</h2>
            <table className="w-full text-[13.5px]">
              <tbody>
                {Object.entries(data.by_theme).map(([theme, value]) => (
                  <tr key={theme} className="border-b border-line last:border-0">
                    <td className="px-5 py-2.5">{theme}</td>
                    <td className="px-5 py-2.5 text-right font-medium tabular-nums">
                      {value === null ? "—" : `${Math.round(value)}%`}
                    </td>
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
