import { useQuery } from "@tanstack/react-query"
import { api } from "./client"

export type GroupRow = { name: string; total: number; compliant: number; readiness: number | null; code?: string | null }

export type FrameworkRow = {
  code: string
  name: string
  version: string
  total: number
  compliant: number
  readiness: number | null
  status_counts: Record<string, number>
  excluded: number
  groups: GroupRow[]
}

export type RiskCard = { open: number; in_progress: number; closed: number; total: number; by_level: Record<string, number> }

export type Dashboard = {
  frameworks: FrameworkRow[]
  evidence: { needs_attention: number; ok: number; total: number }
  risks: RiskCard | null
  unowned_controls: number
  trend: { date: string; readiness: number }[]
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") })
}

export const isNia = (f: Pick<FrameworkRow, "code">) => f.code.startsWith("nia")

/** Bold display name and trailing note: "NIA v2.1" reads as one name; ISO keeps "2022" as a quiet suffix. */
export function frameworkTitle(f: Pick<FrameworkRow, "code" | "name" | "version">): { name: string; note: string } {
  return isNia(f) ? { name: `${f.name} v${f.version}`, note: "" } : { name: f.name, note: f.version }
}
