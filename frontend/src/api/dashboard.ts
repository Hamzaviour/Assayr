import { useQuery } from "@tanstack/react-query"
import { api } from "./client"

export type GroupRow = { name: string; total: number; compliant: number; readiness: number | null }

export type FrameworkRow = {
  code: string
  name: string
  version: string
  total: number
  compliant: number
  readiness: number | null
  status_counts: Record<string, number>
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
