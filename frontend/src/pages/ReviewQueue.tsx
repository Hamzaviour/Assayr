import { useState } from "react"
import { useDecision, useLink, useReviewQueue } from "../api/evidence"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { Icon } from "../components/icons"
import { formatDate } from "../lib/format"

const TONE: Record<string, string> = { pass: "text-ok", warn: "text-warn", fail: "text-bad", skipped: "text-fg-3" }

export function ReviewQueuePage() {
  const queue = useReviewQueue()
  const [selected, setSelected] = useState<string | null>(null)
  const items = queue.data ?? []
  const current = items.find((i) => i.link_id === selected)?.link_id ?? items[0]?.link_id

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Evidence</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Review queue</h1>
      </header>
      {queue.isError && <p role="alert">{queue.error.message}</p>}
      {queue.isSuccess && items.length === 0 && (
        <section className="rounded-xl border border-line bg-surface p-10 text-center">
          <p className="font-semibold">The review queue is clear.</p>
          <p className="text-[13px] text-fg-3">Evidence the checks can't decide on will appear here.</p>
        </section>
      )}
      {items.length > 0 && (
        <section className="grid overflow-hidden rounded-xl border border-line bg-surface md:grid-cols-[300px_minmax(0,1fr)]">
          <ul className="border-b border-line md:border-b-0 md:border-r">
            {items.map((item) => (
              <li key={item.link_id}>
                <button type="button" onClick={() => setSelected(item.link_id)} aria-current={item.link_id === current}
                  className="block w-full border-b border-line px-4 py-3 text-left hover:bg-subtle aria-[current=true]:bg-primary-soft">
                  <span className="block truncate font-mono text-[12.5px] font-medium">{item.filename}</span>
                  <span className="block text-[12px] text-fg-3"><ControlId code={item.control_code} /> · {item.slot_name}</span>
                  <span className="block text-[12px] text-fg-3">
                    {item.uploaded_by ?? "Unknown"} · {formatDate(item.uploaded_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {current && <ReviewDetail key={current} linkId={current} />}
        </section>
      )}
    </div>
  )
}

function ReviewDetail({ linkId }: { linkId: string }) {
  const link = useLink(linkId)
  const decision = useDecision()
  const [reason, setReason] = useState("")
  if (!link.data) return <p role="status" className="p-5 text-fg-3">Loading…</p>
  const l = link.data

  function decide(choice: "accept" | "reject") {
    decision.mutate({ linkId, decision: choice, reason })
  }

  return (
    <div className="grid content-start gap-4 p-5">
      <div>
        <p className="font-mono text-[13px] text-fg-3">{l.control_code} · {l.control_title}</p>
        <h2 className="text-[17px] font-semibold">{l.slot_name}</h2>
        <a className="text-[13px] text-primary underline" href={`/api/v1/artefact-versions/${l.version_id}/download`}>
          Download {l.filename}
        </a>
      </div>
      <ul className="grid gap-1.5 text-[13px]">
        {l.rules.map((rule) => (
          <li key={rule.seq} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2">
            <span className={TONE[rule.status]}><Icon name={rule.status} /></span>
            <div><span className="font-medium">{rule.name}</span><span className="text-fg-2"> — {rule.reason}</span></div>
          </li>
        ))}
      </ul>
      {l.text_preview && (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-subtle p-3 font-mono text-[12px]">
          {l.text_preview}
        </pre>
      )}
      <label htmlFor="review-reason" className="text-[13px] font-medium">Reason</label>
      <textarea id="review-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
        className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
        placeholder="Required when rejecting, or when accepting despite failed checks" />
      {decision.isError && <p role="alert" className="text-[13px] text-bad">{decision.error.message}</p>}
      <div className="flex gap-2">
        <Button onClick={() => decide("accept")} disabled={decision.isPending}>Accept</Button>
        <Button variant="secondary" onClick={() => decide("reject")} disabled={decision.isPending}>Reject</Button>
      </div>
    </div>
  )
}
