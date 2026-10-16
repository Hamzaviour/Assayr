import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export type AuditFramework = "iso27001" | "nia-2.1"
export type AuditResult = "pass" | "fail" | "partial" | "na"
export type TestType = "DA" | "OEA" | "Both"

type Person = { id: string; full_name: string }

export type AuditCounts = { total: number; tested: number; pass: number; partial: number; fail: number; na: number }

export type Audit = {
  id: string
  framework: AuditFramework
  title: string
  period_start: string | null
  period_end: string | null
  auditor: Person | null
  scope_note: string | null
  conclusion: string | null
  status: "draft" | "in_progress" | "completed"
  completed_at: string | null
  completed_by: Person | null
  created_at: string
  counts: AuditCounts
  can_write: boolean
  can_reopen: boolean
}

export type AuditItem = {
  id: string
  ref: string
  sort_order: number
  domain: string
  sub_domain: string
  assessment_area: string | null
  test_type: TestType | null
  requirement: "M" | "A" | null
  result: AuditResult | null
  notes: string | null
}

export type AuditDetail = Audit & { items: AuditItem[] }

export const FRAMEWORK_LABEL: Record<AuditFramework, string> = { iso27001: "ISO/IEC 27001", "nia-2.1": "NIA v2.1" }
export const AUDIT_STATUS_LABEL: Record<Audit["status"], string> = {
  draft: "Draft",
  in_progress: "In progress",
  completed: "Completed",
}
export const RESULT_LABEL: Record<AuditResult, string> = { pass: "Pass", partial: "Partial", fail: "Fail", na: "NA" }

export const auditExportUrl = (id: string) => `/api/v1/audits/${id}/export.xlsx`

export function useAudits() {
  return useQuery({ queryKey: ["audits"], queryFn: () => api<Audit[]>("/audits") })
}

export function useAudit(id: string) {
  return useQuery({ queryKey: ["audit", id], queryFn: () => api<AuditDetail>(`/audits/${id}`) })
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["audits"] })
    queryClient.invalidateQueries({ queryKey: ["audit"] })
  }
}

export function useCreateAudit() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { framework: AuditFramework; title: string }) =>
      api<Audit>("/audits", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: refresh,
  })
}

export function useImportAudit() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ framework, file }: { framework: AuditFramework; file: File }) => {
      const form = new FormData()
      form.append("framework", framework)
      form.append("file", file)
      return api<{ audit: Audit; imported: number; unknown_refs: string[]; skipped_rows: string[] }>("/audits/import", { method: "POST", body: form })
    },
    onSuccess: refresh,
  })
}

export type AuditChanges = Partial<{
  title: string
  period_start: string | null
  period_end: string | null
  auditor_id: string | null
  scope_note: string | null
  conclusion: string | null
}>

export function useUpdateAudit(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (changes: AuditChanges) => api<Audit>(`/audits/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: refresh,
  })
}

export function useAddAuditItems(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { all: true } | { domain: string } | { refs: string[] }) =>
      api<Audit>(`/audits/${id}/items`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: refresh,
  })
}

export function useUpdateAuditItem(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, changes }: { itemId: string; changes: Partial<Omit<AuditItem, "id" | "ref" | "sort_order">> }) =>
      api<AuditItem>(`/audits/${id}/items/${itemId}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: (item) => {
      queryClient.setQueryData<AuditDetail>(["audit", id], (old) =>
        old ? { ...old, items: old.items.map((i) => (i.id === item.id ? item : i)) } : old,
      )
      queryClient.invalidateQueries({ queryKey: ["audit", id] })
      queryClient.invalidateQueries({ queryKey: ["audits"] })
    },
  })
}

export function useRemoveAuditItem(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (itemId: string) => api<Audit>(`/audits/${id}/items/${itemId}`, { method: "DELETE" }),
    onSuccess: refresh,
  })
}

export function useCompleteAudit(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => api<Audit>(`/audits/${id}/complete`, { method: "POST" }), onSuccess: refresh })
}

export function useReopenAudit(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (reason: string) => api<Audit>(`/audits/${id}/reopen`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: refresh,
  })
}
