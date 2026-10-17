import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Owner } from "./types"

export type Grade = "major" | "minor" | "observation" | "ofi"
export type FindingStatus = "open" | "action_planned" | "awaiting_verification" | "closed"

export interface Finding {
  id: string
  code: string
  title: string
  grade: Grade
  status: FindingStatus
  source: string
  framework: string | null
  ref: string | null
  owner: Owner | null
  due_date: string | null
  overdue: boolean
  audit: { id: string; title: string } | null
  audit_item_id: string | null
  actions_open: number
  actions_total: number
  risk: { id: string; code: string } | null
  raised_at: string
  closed_at: string | null
}

export interface ActionFile {
  id: string
  filename: string
  size: number
  uploaded_by: Owner | null
  uploaded_at: string
}

export interface CorrectiveAction {
  id: string
  seq: number
  description: string
  owner: Owner | null
  due_date: string | null
  status: "open" | "done"
  overdue: boolean
  done_at: string | null
  done_note: string | null
  files: ActionFile[]
  can_edit: boolean
  can_complete: boolean
}

export interface Verification {
  verifier: Owner | null
  effective: boolean
  note: string
  verified_at: string
}

export interface FindingDetail extends Finding {
  description: string | null
  root_cause: string | null
  correction: string | null
  response: string | null
  raised_by: Owner | null
  actions: CorrectiveAction[]
  verifications: Verification[]
  can_edit: boolean
  can_edit_capa: boolean
  can_add_action: boolean
  can_verify: boolean
  can_close: boolean
  can_reopen: boolean
  can_raise_risk: boolean
}

export type FindingSummary = {
  open: number
  overdue: number
  by_grade: Record<Grade, number>
  by_status: Record<FindingStatus, number>
}

export const GRADE_LABEL: Record<Grade, string> = {
  major: "Major nonconformity",
  minor: "Minor nonconformity",
  observation: "Observation",
  ofi: "Opportunity for improvement",
}
export const isNonconformity = (grade: Grade) => grade === "major" || grade === "minor"

export const findingsExportUrl = "/api/v1/findings/export.xlsx"
export const actionFileUrl = (findingId: string, actionId: string, fileId: string) =>
  `/api/v1/findings/${findingId}/actions/${actionId}/files/${fileId}`

export function useFindings() {
  return useQuery({ queryKey: ["findings"], queryFn: () => api<Finding[]>("/findings") })
}

export function useFinding(id: string) {
  return useQuery({ queryKey: ["finding", id], queryFn: () => api<FindingDetail>(`/findings/${id}`) })
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    for (const key of ["findings", "finding", "audit", "audits", "dashboard", "risks"]) {
      queryClient.invalidateQueries({ queryKey: [key] })
    }
  }
}

const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) })

export function useRaiseFinding() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (auditItemId: string) => post<FindingDetail>("/findings", { audit_item_id: auditItemId }),
    onSuccess: refresh,
  })
}

export function useRaiseAuditFindings(auditId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: () => post<{ created: Finding[]; existing: number }>(`/audits/${auditId}/findings`, { all: true }),
    onSuccess: refresh,
  })
}

export type FindingChanges = Partial<{
  title: string
  description: string | null
  grade: Grade
  owner_id: string | null
  due_date: string | null
  root_cause: string | null
  correction: string | null
  response: string | null
}>

export function useUpdateFinding(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (changes: FindingChanges) =>
      api<FindingDetail>(`/findings/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: refresh,
  })
}

export function useAddAction(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { description: string; owner_id: string | null; due_date: string | null }) =>
      post<CorrectiveAction>(`/findings/${id}/actions`, body),
    onSuccess: refresh,
  })
}

export function useUpdateAction(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ actionId, changes }: { actionId: string; changes: Partial<{ status: "open" | "done"; done_note: string | null; description: string; owner_id: string | null; due_date: string | null }> }) =>
      api<CorrectiveAction>(`/findings/${id}/actions/${actionId}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: refresh,
  })
}

export function useDeleteAction(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (actionId: string) => api<void>(`/findings/${id}/actions/${actionId}`, { method: "DELETE" }),
    onSuccess: refresh,
  })
}

export function useUploadActionFile(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ actionId, file }: { actionId: string; file: File }) => {
      const form = new FormData()
      form.append("file", file)
      return api<CorrectiveAction>(`/findings/${id}/actions/${actionId}/files`, { method: "POST", body: form })
    },
    onSuccess: refresh,
  })
}

export function useDeleteActionFile(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ actionId, fileId }: { actionId: string; fileId: string }) =>
      api<void>(`/findings/${id}/actions/${actionId}/files/${fileId}`, { method: "DELETE" }),
    onSuccess: refresh,
  })
}

export function useVerifyFinding(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { effective: boolean; note: string }) => post<FindingDetail>(`/findings/${id}/verify`, body),
    onSuccess: refresh,
  })
}

export function useCloseFinding(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (response: string) => post<FindingDetail>(`/findings/${id}/close`, { response }),
    onSuccess: refresh,
  })
}

export function useReopenFinding(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (reason: string) => post<FindingDetail>(`/findings/${id}/reopen`, { reason }),
    onSuccess: refresh,
  })
}

export function useRaiseFindingRisk(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => post<FindingDetail>(`/findings/${id}/raise-risk`), onSuccess: refresh })
}
