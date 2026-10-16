import { useParams } from "@tanstack/react-router"
import { useAudit } from "../api/audits"

export function AuditDetailPage() {
  const { id } = useParams({ from: "/app/audits/$id" })
  const audit = useAudit(id)
  if (audit.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (audit.isError) return <p role="alert">{audit.error.message}</p>
  return <h1 className="font-display text-[28px] font-extrabold tracking-tight">{audit.data.title}</h1>
}
