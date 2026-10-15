import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type {
  ControlPage, Methodology, RiskDetail, RiskLibrary, RiskRow, RiskTask, SnapshotCompare, SnapshotSummary,
} from "./types"

export const RISK_STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  assessed: "Assessed",
  reassessing: "Reassessing",
  treatment_planned: "Treatment planned",
  in_treatment: "In treatment",
  treated: "Treated",
  accepted: "Accepted",
  review_due: "Review due",
  closed: "Closed",
}
export const TREATMENT_LABEL: Record<string, string> = { modify: "Modify", retain: "Retain", avoid: "Avoid", share: "Share" }
export const AUTHORITY_LABEL: Record<string, string> = {
  risk_owner: "the risk owner",
  isms_manager: "an ISMS manager",
  executive: "top management",
}
export const TASK_STATUS_LABEL: Record<string, string> = {
  todo: "To do", in_progress: "In progress", blocked: "Blocked", done: "Done", cancelled: "Cancelled",
}

const path = (code: string) => `/risks/${encodeURIComponent(code)}`
const send = <T,>(url: string, method: string, body?: unknown) =>
  api<T>(url, { method, body: body === undefined ? undefined : JSON.stringify(body) })

export function useMethodology() {
  return useQuery({ queryKey: ["risk-methodology"], queryFn: () => api<Methodology>("/risk-methodology"), staleTime: Infinity })
}

export function useRiskLibrary() {
  return useQuery({ queryKey: ["risk-library"], queryFn: () => api<RiskLibrary>("/risk-library"), staleTime: 300_000 })
}

export function useRisks(filters: { q?: string; owner?: "me" | "none" }) {
  return useQuery({
    queryKey: ["risks", filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.q) params.set("q", filters.q)
      if (filters.owner) params.set("owner", filters.owner)
      const query = params.toString()
      return api<RiskRow[]>(`/risks${query ? `?${query}` : ""}`)
    },
  })
}

export function useRisk(code: string) {
  return useQuery({ queryKey: ["risk", code], queryFn: () => api<RiskDetail>(path(code)) })
}

export function useAllControls() {
  return useQuery({
    queryKey: ["controls", "all"],
    queryFn: async () => (await api<ControlPage>("/controls?limit=200")).items,
    staleTime: 60_000,
  })
}

function useRiskMutation<T>(request: (body: T) => Promise<RiskDetail>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: (detail) => {
      queryClient.setQueryData(["risk", detail.code], detail)
      queryClient.invalidateQueries({ queryKey: ["risks"] })
      queryClient.invalidateQueries({ queryKey: ["soa"] })
    },
  })
}

export function useCreateRisk() {
  return useRiskMutation((body: { template_code?: string; title?: string; owner_id?: string }) =>
    send<RiskDetail>("/risks", "POST", body))
}

export type RiskChanges = Partial<{
  title: string
  description: string | null
  category: string | null
  approach: string
  owner_id: string | null
  threat_codes: string[]
  vulnerability_codes: string[]
  asset_ids: string[]
}>

export function useUpdateRisk(code: string) {
  return useRiskMutation((changes: RiskChanges) => send<RiskDetail>(path(code), "PATCH", changes))
}

export function useSetRiskControls(code: string) {
  return useRiskMutation((body: { links: { code: string; axis: string }[] }) =>
    send<RiskDetail>(`${path(code)}/controls`, "PUT", body))
}

export type AssessmentChanges = Partial<{
  likelihood: number | null
  consequence: Record<string, number>
  current_l: number | null
  current_c: number | null
  current_reason: string | null
  target_l: number | null
  target_c: number | null
  rationale: string | null
}>

export function useSaveAssessment(code: string) {
  return useRiskMutation((changes: AssessmentChanges) =>
    send<RiskDetail>(`${path(code)}/assessment`, "PATCH", changes))
}

export function useFinalizeAssessment(code: string) {
  return useRiskMutation((_body: void) => send<RiskDetail>(`${path(code)}/assessment/finalize`, "POST"))
}

export function useSetTreatment(code: string) {
  return useRiskMutation((body: { option: string; note: string | null; budget: string | null; due: string | null }) =>
    send<RiskDetail>(`${path(code)}/treatment`, "POST", body))
}

export function useAddAction(code: string) {
  return useRiskMutation((body: { title: string; assignee_id: string | null; due: string | null }) =>
    send<RiskDetail>(`${path(code)}/actions`, "POST", body))
}

export function useAcceptRisk(code: string) {
  return useRiskMutation((statement: string) => send<RiskDetail>(`${path(code)}/accept`, "POST", { statement }))
}

export function useCloseRisk(code: string) {
  return useRiskMutation((reason: string) => send<RiskDetail>(`${path(code)}/close`, "POST", { reason }))
}

export function useUpdateTask(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; status?: string; title?: string }) =>
      send<RiskTask>(`/tasks/${id}`, "PATCH", changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk", code] })
      queryClient.invalidateQueries({ queryKey: ["risks"] })
    },
  })
}

export function useSnapshots() {
  return useQuery({ queryKey: ["risk-snapshots"], queryFn: () => api<SnapshotSummary[]>("/risk-snapshots") })
}

export function useCreateSnapshot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (label: string) => send<SnapshotSummary>("/risk-snapshots", "POST", { label }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risk-snapshots"] }),
  })
}

export function useSnapshotCompare(base: string, head: string) {
  return useQuery({
    queryKey: ["risk-snapshots", "compare", base, head],
    queryFn: () => api<SnapshotCompare>(`/risk-snapshots/compare?base=${base}&head=${head}`),
    enabled: Boolean(base && head && base !== head),
  })
}
