import { usePrivacySummary } from "../../api/privacy"
import { usePdppl } from "../../api/privacy2"
import { ProgressBar } from "../../components/charts"

export type PrivacyTab = "overview" | "activities" | "inventory" | "requests" | "breaches" | "processors" | "pdppl"

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export function Overview({ go, sensitive }: { go: (tab: PrivacyTab) => void; sensitive: boolean }) {
  const summary = usePrivacySummary()
  const pdppl = usePdppl()
  const s = summary.data
  type Item = { show: boolean; text: string; tab: PrivacyTab; tone: string }
  const all: Item[] = s
    ? [
        { show: sensitive && s.requests_overdue > 0, text: `${plural(s.requests_overdue, "data subject request", "data subject requests")} overdue`, tab: "requests", tone: "bad" },
        { show: sensitive && s.notifications_overdue > 0, text: `${plural(s.notifications_overdue, "breach notification", "breach notifications")} overdue`, tab: "breaches", tone: "bad" },
        { show: s.dpia_due > 0, text: `${plural(s.dpia_due, "DPIA", "DPIAs")} to approve`, tab: "activities", tone: "warn" },
        { show: s.processors_without_dpa > 0, text: `${plural(s.processors_without_dpa, "processor", "processors")} without an agreement`, tab: "processors", tone: "warn" },
        { show: s.reviews_due > 0, text: `${plural(s.reviews_due, "processing activity", "processing activities")} due for review`, tab: "activities", tone: "warn" },
        { show: sensitive && s.breaches_open > 0, text: `${plural(s.breaches_open, "breach", "breaches")} still open`, tab: "breaches", tone: "warn" },
      ]
    : []
  const items = all.filter((i) => i.show)

  return (
    <div className="grid gap-5 p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section aria-labelledby="attention-title" className="grid content-start gap-2">
        <h2 id="attention-title" className="text-[15px] font-semibold">Needs attention</h2>
        {summary.isSuccess && items.length === 0 && (
          <p className="rounded-xl bg-ok-soft px-4 py-3 text-[13.5px] font-medium text-ok">Nothing needs attention right now.</p>
        )}
        <ul aria-label="Needs attention" className="grid gap-2">
          {items.map((i) => (
            <li key={i.text}>
              <button
                type="button"
                onClick={() => go(i.tab)}
                className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-[13.5px] font-medium transition-colors ${
                  i.tone === "bad" ? "border-bad/30 bg-bad-soft text-bad hover:bg-bad-soft/70" : "border-warn/30 bg-warn-soft text-warn hover:bg-warn-soft/70"
                }`}
              >
                <span aria-hidden="true" className={`size-2 rounded-full ${i.tone === "bad" ? "bg-bad" : "bg-warn"}`} />
                <span className="flex-1">{i.text}</span>
                <span aria-hidden="true">→</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="pdppl-score-title" className="grid content-start gap-3 rounded-xl border border-line p-4">
        <h2 id="pdppl-score-title" className="text-[15px] font-semibold">PDPPL obligations</h2>
        {pdppl.data && (
          <>
            <p className="font-display text-[34px] font-extrabold leading-none text-primary tabular-nums">
              {pdppl.data.total ? Math.round((100 * pdppl.data.compliant) / pdppl.data.total) : 0}%
            </p>
            <ProgressBar value={pdppl.data.compliant} max={pdppl.data.total} label="PDPPL obligations met" color="var(--ok)" />
            <p className="text-[12.5px] text-fg-2">
              {pdppl.data.compliant} of {pdppl.data.total} obligations met.{" "}
              <button type="button" onClick={() => go("pdppl")} className="font-semibold text-primary hover:underline">
                See the obligations
              </button>
            </p>
          </>
        )}
      </section>
    </div>
  )
}
