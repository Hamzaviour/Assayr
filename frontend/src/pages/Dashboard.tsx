import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { type Dashboard, type FrameworkRow, type RiskCard, useDashboard } from "../api/dashboard"
import { useMe } from "../auth/session"
import { BarChart, Donut, LineChart, ProgressBar, type Segment, StackedBar } from "../components/charts"

const STATUS: [string, string, string][] = [
  ["compliant", "Compliant", "var(--ok)"],
  ["in_review", "In review", "var(--review)"],
  ["in_progress", "In progress", "var(--chart-3)"],
  ["at_risk", "At risk", "var(--warn)"],
  ["non_compliant", "Non-compliant", "var(--bad)"],
  ["not_started", "Not started", "var(--idle)"],
]
const LEVELS: [string, string, string][] = [
  ["low", "Low", "var(--heat-1)"],
  ["medium", "Medium", "var(--heat-3)"],
  ["high", "High", "var(--heat-4)"],
  ["critical", "Critical", "var(--heat-5)"],
]
const CARD = "rounded-xl border border-line bg-surface p-5"
const SECTION_TITLE = "font-display text-[18px] font-semibold tracking-tight"
const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value)}%`)

function statusSegments(counts: Record<string, number>): Segment[] {
  return STATUS.map(([key, label, color]) => ({ key, label, color, value: counts[key] ?? 0 }))
}

function FrameworkCard({ f }: { f: FrameworkRow }) {
  return (
    <article className={`${CARD} grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]`}>
      <div className="grid content-start gap-3">
        <p className="flex items-baseline justify-between gap-3">
          <Link to="/compliance" className="text-[17px] hover:underline">
            <strong>{f.name}</strong> <span className="text-fg-3">{f.version}</span>
          </Link>
          <span className="font-display text-[30px] font-extrabold leading-none tabular-nums">{percent(f.readiness)}</span>
        </p>
        <ProgressBar value={f.compliant} max={f.total} label={`${f.name} controls compliant`} />
        <p className="text-[13px] text-fg-2">
          {f.compliant} controls compliant · {f.total} total
        </p>
        {f.readiness === null && (
          <p className="text-[13px] text-fg-3">Upload the first evidence to a control to see readiness here.</p>
        )}
      </div>
      <div className="grid content-start gap-2">
        <p className="text-[12.5px] font-medium text-fg-3">Where every control stands</p>
        <StackedBar segments={statusSegments(f.status_counts)} label={`${f.name} controls by status`} />
      </div>
    </article>
  )
}

function Monitor({
  title,
  attention,
  footLeft,
  total,
  link,
  children,
}: {
  title: string
  attention: number
  footLeft: string
  total: number
  link: ReactNode
  children?: ReactNode
}) {
  return (
    <section className={`${CARD} grid content-start gap-3`}>
      <h3 className="text-[15px] font-semibold">{title}</h3>
      <div>
        <p className="text-[12.5px] text-fg-3">Needs attention</p>
        <p className="font-display text-[30px] font-extrabold leading-tight tabular-nums">{attention}</p>
      </div>
      {children ?? <ProgressBar value={total - attention} max={total} label={`${title} in good order`} color="var(--ok)" />}
      <p className="flex justify-between text-[12.5px] text-fg-2">
        <span>{footLeft}</span>
        <span>{total} total</span>
      </p>
      {link}
    </section>
  )
}

const LINK = "text-[13px] font-medium text-primary hover:underline"

function riskSegments(r: RiskCard): Segment[] {
  return [
    { key: "open", label: "Open", value: r.open, color: "var(--bad)" },
    { key: "in_progress", label: "In progress", value: r.in_progress, color: "var(--warn)" },
    { key: "closed", label: "Closed", value: r.closed, color: "var(--ok)" },
  ]
}

function Body({ d }: { d: Dashboard }) {
  const iso = d.frameworks[0]
  return (
    <>
      <section className="grid gap-3" aria-labelledby="compliance-title">
        <h2 id="compliance-title" className={SECTION_TITLE}>Compliance</h2>
        {d.frameworks.map((f) => (
          <FrameworkCard key={f.code} f={f} />
        ))}
      </section>

      <section className="grid gap-3" aria-labelledby="monitoring-title">
        <h2 id="monitoring-title" className={SECTION_TITLE}>Monitoring</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <Monitor
            title="Evidence"
            attention={d.evidence.needs_attention}
            footLeft={`${d.evidence.ok} accepted`}
            total={d.evidence.total}
            link={<Link to="/evidence" className={LINK}>Review evidence →</Link>}
          />
          {d.risks && (
            <Monitor
              title="Risks"
              attention={d.risks.open}
              footLeft={`${d.risks.closed} closed`}
              total={d.risks.total}
              link={<Link to="/risks" className={LINK}>Open the risk register →</Link>}
            >
              <StackedBar segments={riskSegments(d.risks)} label="Risks by status" />
            </Monitor>
          )}
          <Monitor
            title="Control owners"
            attention={d.unowned_controls}
            footLeft={`${iso.total - d.unowned_controls} assigned`}
            total={iso.total}
            link={<Link to="/controls" search={{ owner: "none" }} className={LINK}>Assign owners →</Link>}
          />
        </div>
      </section>

      <section className="grid gap-3" aria-labelledby="trends-title">
        <h2 id="trends-title" className={SECTION_TITLE}>Trends</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <div className={CARD}>
            <h3 className="mb-3 text-[15px] font-semibold">Readiness</h3>
            <LineChart
              points={d.trend.map((p) => ({ x: p.date, y: p.readiness }))}
              label="Readiness over the last 90 days"
              format={(y) => `${Math.round(y)}%`}
            />
            {d.trend.length === 0 && (
              <p className="mt-2 text-[13px] text-fg-3">The trend appears after the first daily snapshot.</p>
            )}
          </div>
          <div className={CARD}>
            <h3 className="mb-3 text-[15px] font-semibold">Controls</h3>
            <Donut segments={statusSegments(iso.status_counts)} label="Controls by status" centre={percent(iso.readiness)} />
          </div>
          {d.risks && (
            <div className={CARD}>
              <h3 className="mb-3 text-[15px] font-semibold">Risk levels</h3>
              <BarChart
                label="Risks by level"
                bars={LEVELS.map(([key, label, color]) => ({ key, label, color, value: d.risks?.by_level[key] ?? 0 }))}
              />
            </div>
          )}
        </div>
      </section>
    </>
  )
}

export function DashboardPage() {
  const me = useMe()
  const dashboard = useDashboard()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })
  return (
    <div className="mx-auto grid max-w-6xl gap-8">
      <header>
        <p className="mb-1 text-[13px] text-fg-3">{today}</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Welcome, {firstName}</h1>
      </header>
      {dashboard.isPending && <div className="h-40 animate-pulse rounded-xl bg-subtle" aria-label="Loading" />}
      {dashboard.isError && <p role="alert">{dashboard.error.message}</p>}
      {dashboard.data && <Body d={dashboard.data} />}
    </div>
  )
}
