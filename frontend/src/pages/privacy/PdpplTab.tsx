import { useState } from "react"
import { usePdppl } from "../../api/privacy2"
import { ProgressBar } from "../../components/charts"
import { StatusPill } from "../../components/StatusPill"
import { Status } from "../../components/Status"

export function PdpplTab() {
  const pdppl = usePdppl()
  const [gapsOnly, setGapsOnly] = useState(false)
  if (pdppl.isPending) return <p role="status" className="p-6 text-fg-3">Loading…</p>
  if (pdppl.isError) return <p role="alert" className="p-6">{pdppl.error.message}</p>
  const p = pdppl.data
  const shown = p.obligations.filter((o) => !gapsOnly || o.status !== "compliant")
  const topics = p.topics.filter((t) => shown.some((o) => o.topic === t))

  return (
    <div className="grid gap-4 p-5">
      <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="grid gap-1.5">
          <p className="text-[13.5px] font-semibold">{p.title}</p>
          <ProgressBar value={p.compliant} max={p.total} label="PDPPL obligations met" color="var(--ok)" />
          <p className="text-[12.5px] text-fg-2">{p.compliant} of {p.total} obligations met</p>
        </div>
        <button
          type="button"
          aria-pressed={gapsOnly}
          onClick={() => setGapsOnly((v) => !v)}
          className={`rounded-full border px-3 py-1 text-[12.5px] font-semibold ${gapsOnly ? "border-primary bg-primary text-on-primary" : "border-line text-fg-2 hover:bg-subtle"}`}
        >
          Show only gaps
        </button>
      </div>
      <p className="rounded-lg bg-subtle px-3 py-2 text-[12.5px] text-fg-2">{p.notice}</p>
      {topics.map((topic) => (
        <section key={topic} aria-label={topic} className="grid gap-2">
          <h3 className="text-[14px] font-semibold">{topic}</h3>
          <ul className="grid gap-2">
            {shown
              .filter((o) => o.topic === topic)
              .map((o) => (
                <li key={o.ref} className="grid gap-1.5 rounded-xl border border-line p-3 md:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-semibold">
                      <span className="mr-2 font-mono text-[11.5px] text-fg-3">{o.ref}</span>
                      {o.title}
                    </p>
                    <p className="text-[12.5px] text-fg-2">{o.summary}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-fg-2">
                      <Status area="evidence" value={o.evidence.result} />
                      <span>{o.evidence.reason}</span>
                    </p>
                    <p className="mt-1 text-[11.5px] text-fg-3">Controls: {o.iso.map((c) => c.code).join(", ") || "—"}</p>
                  </div>
                  <div className="self-start"><StatusPill status={o.status} /></div>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
