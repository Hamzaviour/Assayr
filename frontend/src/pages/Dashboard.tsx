import { Link } from "@tanstack/react-router"
import type { CSSProperties, ReactNode } from "react"
import { type Dashboard, type FrameworkRow, type RiskCard, useDashboard } from "../api/dashboard"
import { useMethodology } from "../api/risks"
import { useMe } from "../auth/session"
import { BarChart, Donut, LineChart, ProgressBar, type Segment, StackedBar } from "../components/charts"
import { CountUp } from "../components/CountUp"
import { Icon } from "../components/icons"

const STATUS: [string, string, string][] = [
  ["compliant", "Compliant", "var(--ok)"],
  ["in_review", "In review", "var(--review)"],
  ["in_progress", "In progress", "var(--chart-3)"],
  ["at_risk", "At risk", "var(--warn)"],
  ["non_compliant", "Non-compliant", "var(--bad)"],
  ["not_started", "Not started", "var(--idle)"],
]
const HEAT = ["var(--heat-1)", "var(--heat-2)", "var(--heat-3)", "var(--heat-4)", "var(--heat-5)"]
const CARD = "lift relative overflow-hidden rounded-2xl border border-line bg-surface p-5"
/** Staggers the shared entrance animation. */
const order = (i: number) => ({ "--i": i }) as CSSProperties
/** A thin maroon edge along the top of a card: the brand without a loud fill. */
function Edge() {
  return <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
}
const SECTION_TITLE = "font-display text-[19px] font-bold tracking-tight"
const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value)}%`)

function statusSegments(counts: Record<string, number>): Segment[] {
  return STATUS.map(([key, label, color]) => ({ key, label, color, value: counts[key] ?? 0 }))
}

function FrameworkCard({ f }: { f: FrameworkRow }) {
  return (
    <article className={`${CARD} rise grid gap-6 p-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]`} style={order(1)}>
      <Edge />
      <div className="grid content-start gap-3">
        <p className="flex items-baseline justify-between gap-3">
          <Link to="/compliance" className="text-[17px] hover:underline">
            <strong>{f.name}</strong> <span className="text-fg-3">{f.version}</span>
          </Link>
          <span className="font-display text-[34px] font-extrabold leading-none text-brand">
            {f.readiness === null ? "—" : <CountUp value={Math.round(f.readiness)} suffix="%" />}
          </span>
        </p>
        <ProgressBar value={f.compliant} max={f.total} label={`${f.name} controls compliant`} />
        <p className="text-[13px] text-fg-2">
          {f.compliant} controls compliant · {f.total} total
          {f.excluded > 0 && <span className="text-fg-3"> · {f.excluded} excluded in the SoA</span>}
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
  icon,
  index,
}: {
  icon: string
  index: number
  title: string
  attention: number
  footLeft: string
  total: number
  link: ReactNode
  children?: ReactNode
}) {
  return (
    <section className={`${CARD} rise grid content-start gap-3`} style={order(index)}>
      <Edge />
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary">
          <Icon name={icon} size={17} />
        </span>
        <h3 className="text-[15px] font-semibold">{title}</h3>
      </div>
      <div>
        <p className="text-[12.5px] text-fg-3">Needs attention</p>
        <p className={`font-display text-[32px] font-extrabold leading-tight ${attention > 0 ? "text-brand" : ""}`}>
          <CountUp value={attention} />
        </p>
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

const LINK = "group/link inline-flex items-center gap-1 text-[13px] font-semibold text-primary"

function riskSegments(r: RiskCard): Segment[] {
  return [
    { key: "open", label: "Open", value: r.open, color: "var(--bad)" },
    { key: "in_progress", label: "In progress", value: r.in_progress, color: "var(--warn)" },
    { key: "closed", label: "Closed", value: r.closed, color: "var(--ok)" },
  ]
}

function levelBars(risks: RiskCard, bands: { key: string; label: string }[]): Segment[] {
  // Bands come from the methodology, so every level (Very low too) is shown in its order.
  const shown = bands.length ? bands : Object.keys(risks.by_level).map((key) => ({ key, label: key }))
  return shown.map((b, i) => ({
    key: b.key,
    label: b.label,
    color: HEAT[Math.min(HEAT.length - 1, Math.round((i * (HEAT.length - 1)) / Math.max(1, shown.length - 1)))],
    value: risks.by_level[b.key] ?? 0,
  }))
}

function Body({ d }: { d: Dashboard }) {
  const iso = d.frameworks[0]
  const methodology = useMethodology()
  const bands = methodology.data?.bands ?? []
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
            icon="evidence"
            index={3}
            attention={d.evidence.needs_attention}
            footLeft={`${d.evidence.ok} accepted`}
            total={d.evidence.total}
            link={<Link to="/evidence" className={LINK}>Review evidence <span aria-hidden="true" className="transition-transform duration-300 group-hover/link:translate-x-1">→</span></Link>}
          />
          {d.risks && (
            <Monitor
              title="Risks"
            icon="risk"
            index={4}
              attention={d.risks.open}
              footLeft={`${d.risks.closed} closed`}
              total={d.risks.total}
              link={<Link to="/risks" className={LINK}>Open the risk register <span aria-hidden="true" className="transition-transform duration-300 group-hover/link:translate-x-1">→</span></Link>}
            >
              <StackedBar segments={riskSegments(d.risks)} label="Risks by status" />
            </Monitor>
          )}
          <Monitor
            title="Control owners"
            icon="controls"
            index={5}
            attention={d.unowned_controls}
            footLeft={`${iso.total - d.unowned_controls} assigned`}
            total={iso.total}
            link={<Link to="/controls" search={{ owner: "none" }} className={LINK}>Assign owners <span aria-hidden="true" className="transition-transform duration-300 group-hover/link:translate-x-1">→</span></Link>}
          />
        </div>
      </section>

      <section className="grid gap-3" aria-labelledby="trends-title">
        <h2 id="trends-title" className={SECTION_TITLE}>Trends</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <div className={`${CARD} rise`} style={order(6)}>
            <h3 className="mb-3 text-[15px] font-semibold">Readiness</h3>
            <LineChart
              points={d.trend.map((p) => ({ x: p.date, y: p.readiness }))}
              label="Readiness over the last 90 days"
              format={(y) => `${Math.round(y)}%`}
            />
            {d.trend.length < 2 && (
              <p className="mt-2 text-[13px] text-fg-3">
                {d.trend.length === 1 && <b className="text-fg">Today: {Math.round(d.trend[0].readiness)}%. </b>}
                {d.trend.length === 1
                  ? "The trend line appears after the second daily snapshot."
                  : "The trend appears after the first daily snapshot."}
              </p>
            )}
          </div>
          <div className={`${CARD} rise`} style={order(7)}>
            <h3 className="mb-3 text-[15px] font-semibold">Controls</h3>
            <Donut segments={statusSegments(iso.status_counts)} label="Controls by status" centre={percent(iso.readiness)} />
          </div>
          {d.risks && (
            <div className={`${CARD} rise`} style={order(8)}>
              <h3 className="mb-3 text-[15px] font-semibold">Risk levels</h3>
              <BarChart label="Risks by level" bars={levelBars(d.risks, bands)} />
            </div>
          )}
        </div>
      </section>
    </>
  )
}

function Welcome({ firstName, today, d }: { firstName: string; today: string; d?: Dashboard }) {
  const iso = d?.frameworks[0]
  const attention = d ? d.evidence.needs_attention + (d.risks?.open ?? 0) : 0
  const action = "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-colors duration-200"
  return (
    <header className="brand-surface rise relative overflow-hidden rounded-2xl px-6 py-7 text-on-brand-2 md:px-9 md:py-9" style={order(0)}>
      <div className="relative grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="grid gap-2">
          <h1 className="font-display text-[28px] font-extrabold tracking-tight text-on-brand md:text-[34px]">
            Welcome, {firstName}
          </h1>
          <p className="max-w-xl text-[15px]">
            {iso
              ? iso.readiness === null
                ? `${today}. Your ${iso.name} readiness appears here as evidence is verified.`
                : `${today}. ${iso.name} is ${Math.round(iso.readiness)}% ready${attention ? `, and ${attention} item${attention === 1 ? " needs" : "s need"} your attention.` : ", with nothing waiting on you."}`
              : today}
          </p>
        </div>
        <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
          <Link to="/evidence" className={`${action} bg-white text-brand hover:bg-on-brand-2`}>
            <Icon name="evidence" size={16} /> Review evidence
          </Link>
          <Link to="/risks" className={`${action} bg-white/12 text-on-brand ring-1 ring-white/25 hover:bg-white/20`}>
            <Icon name="risk" size={16} /> Risk register
          </Link>
        </nav>
      </div>
    </header>
  )
}

export function DashboardPage() {
  const me = useMe()
  const dashboard = useDashboard()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })
  return (
    <div className="mx-auto grid max-w-6xl gap-9">
      <Welcome firstName={firstName} today={today} d={dashboard.data} />
      {dashboard.isPending && <div className="h-40 animate-pulse rounded-2xl bg-subtle" aria-label="Loading" />}
      {dashboard.isError && <p role="alert">{dashboard.error.message}</p>}
      {dashboard.data && <Body d={dashboard.data} />}
    </div>
  )
}
