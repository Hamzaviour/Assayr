import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export type DocType = "policy" | "procedure" | "guideline"
export const DOC_TYPES: { type: DocType; label: string; singular: string; prefix: string }[] = [
  { type: "policy", label: "Policies", singular: "policy", prefix: "POL" },
  { type: "procedure", label: "Procedures", singular: "procedure", prefix: "PRO" },
  { type: "guideline", label: "Guidelines", singular: "guideline", prefix: "GUI" },
]

type Person = { id: string; full_name: string }

export type DocumentRow = {
  id: string
  doc_type: DocType
  code: string
  title: string
  description: string | null
  owner: Person | null
  status: "draft" | "approved" | "retired"
  version_label: string
  approved_by: Person | null
  approved_at: string | null
  review_due: string | null
  review_overdue: boolean
  filename: string | null
  size: number | null
  can_edit: boolean
  can_approve: boolean
}

export type DocumentDetail = DocumentRow & {
  controls: { code: string; title: string; status: string }[]
  history: { at: string; actor: string | null; action: string }[]
}

export type ControlDocument = Pick<DocumentRow, "id" | "code" | "title" | "status" | "version_label" | "review_due">
export type ControlDocuments = Record<DocType, ControlDocument[]>

export const documentFileUrl = (id: string) => `/api/v1/documents/${id}/file`

export function useDocuments() {
  return useQuery({ queryKey: ["documents"], queryFn: () => api<DocumentRow[]>("/documents") })
}

export function useDocument(id: string) {
  return useQuery({ queryKey: ["document", id], queryFn: () => api<DocumentDetail>(`/documents/${id}`) })
}

const controlDocsKey = (code: string) => ["control-documents", code]
const controlDocsPath = (code: string) => `/controls/${encodeURIComponent(code)}/documents`

/** Documents linked to each of the given controls, merged per type (a document linked twice shows once). */
export function useControlDocuments(codes: string[]) {
  const results = useQueries({
    queries: codes.map((code) => ({
      queryKey: controlDocsKey(code),
      queryFn: () => api<ControlDocuments>(controlDocsPath(code)),
    })),
  })
  const merged: ControlDocuments = { policy: [], procedure: [], guideline: [] }
  const seen = new Set<string>()
  for (const r of results) {
    for (const { type } of DOC_TYPES) {
      for (const d of r.data?.[type] ?? []) {
        if (seen.has(d.id)) continue
        seen.add(d.id)
        merged[type].push(d)
      }
    }
  }
  return {
    data: merged,
    isPending: results.some((r) => r.isPending),
    error: results.find((r) => r.error)?.error ?? null,
  }
}

function useInvalidateDocuments() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["documents"] })
    queryClient.invalidateQueries({ queryKey: ["document"] })
    queryClient.invalidateQueries({ queryKey: ["control-documents"] })
  }
}

export function useCreateDocument() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: (body: { doc_type: DocType; code: string; title: string; description?: string }) =>
      api<DocumentRow>("/documents", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  })
}

export function useUpdateDocument(id: string) {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: (changes: Partial<{ title: string; description: string | null; code: string; status: "retired"; review_due: string | null }>) =>
      api<DocumentRow>(`/documents/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: invalidate,
  })
}

export function useApproveDocument(id: string) {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: () => api<DocumentRow>(`/documents/${id}/approve`, { method: "POST" }),
    onSuccess: invalidate,
  })
}

export function useUploadDocumentFile(id: string) {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append("file", file)
      return api<DocumentRow>(`/documents/${id}/file`, { method: "POST", body: form })
    },
    onSuccess: invalidate,
  })
}

export function useLinkControlDocument(code: string) {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: ({ id, link }: { id: string; link: boolean }) =>
      api<ControlDocuments>(`${controlDocsPath(code)}/${id}`, { method: link ? "POST" : "DELETE" }),
    onSuccess: (docs) => {
      invalidate()
      queryClient.setQueryData(controlDocsKey(code), docs)
    },
  })
}
