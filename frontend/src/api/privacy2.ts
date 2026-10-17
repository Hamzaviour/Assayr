import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Activity } from "./privacy"

type Person = { id: string; full_name: string }

export type Processor = {
  id: string
  name: string
  service: string | null
  country: string | null
  data_categories: string[]
  dpa_signed: boolean
  dpa_date: string | null
  dpa_document_id: string | null
  subprocessors: string | null
  security_review_on: string | null
  security_result: "satisfactory" | "concerns" | "unsatisfactory" | null
  risk_level: number
  risk_level_label: string
  status: "active" | "ended"
  activities: { id: string; code: string; name: string }[]
  can_edit: boolean
}
export type ProcessorInput = Partial<Omit<Processor, "id" | "risk_level_label" | "activities" | "can_edit">> & { name: string }

export type DpiaRisk = {
  id: string
  title: string
  likelihood: number
  impact: number
  score: number
  level: number
  level_label: string
  measures: string | null
  owner: Person | null
  residual_likelihood: number | null
  residual_impact: number | null
  residual_score: number | null
  residual_level_label: string | null
  risk: { id: string; code: string } | null
}
export type Dpia = {
  id: string
  status: "draft" | "in_review" | "approved"
  screening: Record<string, boolean>
  recommended: boolean
  description: string | null
  necessity: string | null
  consultation: string | null
  conclusion: string | null
  approved_by: Person | null
  approved_at: string | null
  review_due: string | null
  risks: DpiaRisk[]
  can_edit: boolean
}
export const SCREENING: Record<string, string> = {
  sensitive: "Sensitive personal data",
  large_scale: "Large scale",
  monitoring: "Systematic monitoring",
  new_tech: "New technology",
  children: "Children's data",
  cross_border: "Transfer outside Qatar",
  automated: "Automated decisions with significant effect",
  combining: "Combining datasets",
}

export type SubjectRequest = {
  id: string
  code: string
  type: string
  requester_name: string
  requester_contact: string | null
  channel: string
  received_on: string
  due_on: string
  days_left: number | null
  overdue: boolean
  identity_verified: boolean
  identity_method: string | null
  assignee: Person | null
  activities: { id: string; code: string; name: string }[]
  steps: { text: string; done: boolean }[]
  response: string | null
  status: "open" | "in_progress" | "closed"
  outcome: string | null
  refusal_reason: string | null
  closed_on: string | null
}
export const REQUEST_TYPE: Record<string, string> = {
  access: "Access",
  correction: "Correction",
  erasure: "Erasure",
  objection: "Objection",
  restriction: "Restriction",
  withdraw_consent: "Withdraw consent",
  other: "Other",
}
export const REQUEST_OUTCOME: Record<string, string> = {
  fulfilled: "Fulfilled",
  partially: "Partially fulfilled",
  refused: "Refused",
  withdrawn: "Withdrawn",
}

export type Breach = {
  id: string
  code: string
  title: string
  discovered_at: string
  occurred_at: string | null
  description: string | null
  data_categories: string[]
  people_affected: number | null
  assets: { id: string; code: string; name: string }[]
  activities: { id: string; code: string; name: string }[]
  severity: "low" | "medium" | "high" | "critical"
  severity_level: number
  containment: string | null
  regulator_notify: "required" | "not_required" | "undecided"
  regulator_notified_at: string | null
  people_notify: "required" | "not_required" | "undecided"
  people_notified_at: string | null
  notify_deadline: string
  pending_notifications: string[]
  hours_left: number | null
  notification_overdue: boolean
  lessons: string | null
  status: "open" | "contained" | "closed"
  risk: { id: string; code: string; name: string } | null
}
export const NOTIFY: Record<string, string> = { required: "Required", not_required: "Not required", undecided: "Not decided" }

export type PdpplObligation = {
  ref: string
  topic: string
  title: string
  summary: string
  iso: { code: string; title: string; status: string }[]
  evidence: { result: "met" | "partial" | "missing" | "na"; reason: string }
  status: string
}
export type Pdppl = { name: string; title: string; notice: string; topics: string[]; total: number; compliant: number; obligations: PdpplObligation[] }

function useSave<T, R>(fn: (body: T) => Promise<R>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["privacy"] })
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export const useProcessors = () =>
  useQuery({ queryKey: ["privacy", "processors"], queryFn: () => api<Processor[]>("/privacy/processors") })
export const useCreateProcessor = () =>
  useSave((body: ProcessorInput) => api<Processor>("/privacy/processors", { method: "POST", body: JSON.stringify(body) }))
export const useUpdateProcessor = (id: string) =>
  useSave((body: Partial<ProcessorInput>) =>
    api<Processor>(`/privacy/processors/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  )
export const useLinkActivityProcessors = (activityId: string) =>
  useSave((processor_ids: string[]) =>
    api<Activity>(`/privacy/activities/${activityId}/processors`, { method: "PUT", body: JSON.stringify({ processor_ids }) }),
  )

const dpiaPath = (activityId: string) => `/privacy/activities/${activityId}/dpia`
export const useDpia = (activityId: string) =>
  useQuery({ queryKey: ["privacy", "dpia", activityId], queryFn: () => api<Dpia>(dpiaPath(activityId)), retry: false })
export const useSaveDpia = (activityId: string) =>
  useSave((body: Partial<Pick<Dpia, "screening" | "description" | "necessity" | "consultation" | "conclusion" | "review_due">>) =>
    api<Dpia>(dpiaPath(activityId), { method: "PUT", body: JSON.stringify(body) }),
  )
export const useDpiaAction = (activityId: string) =>
  useSave((action: "submit" | "approve" | "reopen") => api<Dpia>(`${dpiaPath(activityId)}/${action}`, { method: "POST" }))
export const useAddDpiaRisk = (activityId: string) =>
  useSave(
    (body: { title: string; likelihood: number; impact: number; measures?: string | null; residual_likelihood?: number | null; residual_impact?: number | null }) =>
      api<DpiaRisk>(`${dpiaPath(activityId)}/risks`, { method: "POST", body: JSON.stringify(body) }),
  )
export const useRemoveDpiaRisk = (activityId: string) =>
  useSave((riskId: string) => api<Dpia>(`${dpiaPath(activityId)}/risks/${riskId}`, { method: "DELETE" }))
export const useRaiseDpiaRisk = (activityId: string) =>
  useSave((riskId: string) => api<DpiaRisk>(`${dpiaPath(activityId)}/risks/${riskId}/raise`, { method: "POST" }))

export const useRequests = (enabled = true) =>
  useQuery({ queryKey: ["privacy", "requests"], queryFn: () => api<SubjectRequest[]>("/privacy/requests"), enabled })
export const useRequest = (id: string) =>
  useQuery({ queryKey: ["privacy", "request", id], queryFn: () => api<SubjectRequest>(`/privacy/requests/${id}`) })
export const useCreateRequest = () =>
  useSave((body: { type: string; requester_name: string; requester_contact?: string | null; channel: string; received_on: string }) =>
    api<SubjectRequest>("/privacy/requests", { method: "POST", body: JSON.stringify(body) }),
  )
export const useUpdateRequest = (id: string) =>
  useSave((body: Partial<Pick<SubjectRequest, "steps" | "response" | "identity_verified" | "identity_method" | "due_on">>) =>
    api<SubjectRequest>(`/privacy/requests/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  )
export const useCloseRequest = (id: string) =>
  useSave((body: { outcome: string; refusal_reason?: string | null; response?: string | null }) =>
    api<SubjectRequest>(`/privacy/requests/${id}/close`, { method: "POST", body: JSON.stringify(body) }),
  )

export const useBreaches = (enabled = true) =>
  useQuery({ queryKey: ["privacy", "breaches"], queryFn: () => api<Breach[]>("/privacy/breaches"), enabled })
export const useBreach = (id: string) =>
  useQuery({ queryKey: ["privacy", "breach", id], queryFn: () => api<Breach>(`/privacy/breaches/${id}`) })
export const useCreateBreach = () =>
  useSave(
    (body: { title: string; discovered_at: string; severity: string; regulator_notify: string; people_notify: string; people_affected?: number | null }) =>
      api<Breach>("/privacy/breaches", { method: "POST", body: JSON.stringify(body) }),
  )
export const useUpdateBreach = (id: string) =>
  useSave((body: Partial<Breach>) => api<Breach>(`/privacy/breaches/${id}`, { method: "PATCH", body: JSON.stringify(body) }))
export const useRaiseBreachRisk = (id: string) =>
  useSave(() => api<Breach>(`/privacy/breaches/${id}/raise-risk`, { method: "POST" }))

export const usePdppl = () => useQuery({ queryKey: ["privacy", "pdppl"], queryFn: () => api<Pdppl>("/privacy/pdppl") })
