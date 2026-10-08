import { StatusPill } from "./StatusPill"

const MAP: Record<string, [string, string]> = {
  verified: ["compliant", "Verified"],
  expiring: ["at_risk", "Expiring"],
  expired_grace: ["at_risk", "Expired, in grace period"],
  expired: ["non_compliant", "Expired"],
  rejected: ["non_compliant", "Rejected"],
  missing: ["not_started", "Missing"],
}

export function SlotStatePill({ state, artefactState }: { state: string; artefactState?: string }) {
  if (state === "pending") {
    return <StatusPill status="in_review" label={artefactState === "verifying" ? "Verifying" : "Needs review"} />
  }
  const [status, label] = MAP[state] ?? ["not_started", state]
  return <StatusPill status={status} label={label} />
}
