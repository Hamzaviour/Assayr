import { useEffect } from "react"
import { useLink } from "../api/evidence"
import type { ArtefactLink } from "../api/types"
import { formatDate } from "../lib/format"
import { Icon } from "./icons"

const TONE: Record<string, string> = { pass: "text-ok", warn: "text-warn", fail: "text-bad", skipped: "text-fg-3" }

function Verdict({ link }: { link: ArtefactLink }) {
  if (link.state === "accepted") {
    const until = link.expires_on ? ` until ${formatDate(link.expires_on)}` : ""
    return <p className="rounded-lg bg-ok-soft px-3 py-2"><b>Accepted.</b> {link.slot_name} is verified{until}.</p>
  }
  if (link.state === "in_review") {
    return (
      <p className="rounded-lg bg-review-soft px-3 py-2">
        <b>Needs review.</b> The checks weren't conclusive, so a reviewer will decide. You'll see the decision here.
      </p>
    )
  }
  return (
    <p className="rounded-lg bg-bad-soft px-3 py-2">
      <b>Rejected.</b> Fix the failed checks above and upload a new version.
    </p>
  )
}

export function VerificationPanel({ linkId, onDone }: { linkId: string; onDone: () => void }) {
  const query = useLink(linkId)
  const link = query.data
  const done = link !== undefined && link.state !== "verifying"
  useEffect(() => {
    if (done) onDone()
  }, [done, onDone])

  if (!link) return <p role="status" className="px-5 pb-4 text-[13px] text-fg-3">Uploading…</p>
  return (
    <div className="mx-5 mb-4 grid gap-2 rounded-lg border border-line bg-canvas p-3 text-[13px]" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate font-mono font-medium">{link.filename}</span>
        <span className="text-fg-3 tabular-nums">
          {done ? "Checks complete" : `Checking ${link.rules.length} of ${link.rules_planned}`}
        </span>
      </div>
      <ul className="grid gap-1.5">
        {link.rules.map((rule) => (
          <li key={rule.seq} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-start gap-2">
            <span className={TONE[rule.status]}><Icon name={rule.status} /></span>
            <div className="min-w-0">
              <span className="font-medium">{rule.name}</span>
              <span className="text-fg-2"> — {rule.reason}</span>
              {rule.fix_hint && <p className="text-fg-2">{rule.fix_hint}</p>}
            </div>
            <code className="font-mono text-[11px] text-fg-3">{rule.code}</code>
          </li>
        ))}
      </ul>
      {link.confidence !== null && (
        <p className="text-fg-2">Confidence <b className="tabular-nums">{link.confidence.toFixed(2)}</b></p>
      )}
      {done && <Verdict link={link} />}
    </div>
  )
}
