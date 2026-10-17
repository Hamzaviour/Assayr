import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ApiError, api } from "./client"
import type { Owner } from "./types"

export interface AiSystem {
  id: string
  code: string
  name: string
  purpose: string | null
  owner: Owner | null
  source: "in_house" | "third_party" | "open_source"
  provider: string | null
  model_type: string | null
  lifecycle: "planned" | "development" | "validation" | "deployed" | "retired"
  risk_level: number
  risk_label: string
  uses_personal_data: boolean
  pii_categories: string[]
  asset_ids: string[]
  human_oversight: string | null
  status: "active" | "retired"
  assessment_status: "draft" | "in_review" | "approved" | null
  created_at: string
  can_edit: boolean
}
export type AiSystemInput = Partial<Omit<AiSystem, "id" | "code" | "owner" | "risk_label" | "assessment_status" | "created_at" | "can_edit">> & {
  owner_id?: string | null
}

export const SECTIONS = [
  ["intended_use", "Intended use and foreseeable misuse"],
  ["affected", "Affected individuals and groups"],
  ["individual_impacts", "Impacts on individuals"],
  ["societal_impacts", "Societal impacts"],
  ["fairness", "Fairness and bias"],
  ["transparency", "Transparency and explainability"],
  ["oversight", "Human oversight"],
  ["safety", "Safety and reliability"],
  ["data_quality", "Data quality and provenance"],
  ["conclusion", "Conclusion"],
] as const
export type SectionKey = (typeof SECTIONS)[number][0]
export const SOURCE_LABEL: Record<string, string> = {
  in_house: "Built in-house",
  third_party: "Third-party provider",
  open_source: "Open-source model",
}

export interface AiImpact {
  id: string
  area: string
  description: string
  likelihood: number
  impact: number
  score: number
  level: number
  mitigation: string | null
  owner: Owner | null
  risk_id: string | null
  risk_code: string | null
}
export type Assessment = Record<SectionKey, string | null> & {
  id: string
  status: "draft" | "in_review" | "approved"
  approved_by: Owner | null
  approved_at: string | null
  review_due: string | null
  impacts: AiImpact[]
  missing: string[]
  can_edit: boolean
}

export function useAiSystems() {
  return useQuery({ queryKey: ["ai", "systems"], queryFn: () => api<AiSystem[]>("/ai/systems") })
}

export function useAiSystem(id: string) {
  return useQuery({ queryKey: ["ai", "system", id], queryFn: () => api<AiSystem>(`/ai/systems/${id}`) })
}

export function useCreateAiSystem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AiSystemInput) => api<AiSystem>("/ai/systems", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai", "systems"] }),
  })
}

export function useUpdateAiSystem(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AiSystemInput) => api<AiSystem>(`/ai/systems/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (system) => {
      queryClient.setQueryData(["ai", "system", id], system)
      queryClient.invalidateQueries({ queryKey: ["ai", "systems"] })
    },
  })
}

/** 404 means "no assessment yet", which the page shows as a start button rather than an error. */
export function useAssessment(id: string) {
  return useQuery({
    queryKey: ["ai", "assessment", id],
    queryFn: async () => {
      try {
        return await api<Assessment>(`/ai/systems/${id}/assessment`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}

function useAssessmentMutation<T>(id: string, call: (body: T) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: call,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai", "assessment", id] })
      queryClient.invalidateQueries({ queryKey: ["ai", "system", id] })
    },
  })
}

export function useSaveAssessment(id: string) {
  return useAssessmentMutation(id, (body: Partial<Record<SectionKey, string | null>>) =>
    api<Assessment>(`/ai/systems/${id}/assessment`, { method: "PUT", body: JSON.stringify(body) }),
  )
}

export function useAddImpact(id: string) {
  return useAssessmentMutation(id, (body: { area: string; description: string; likelihood: number; impact: number; mitigation?: string | null }) =>
    api<AiImpact>(`/ai/systems/${id}/assessment/impacts`, { method: "POST", body: JSON.stringify(body) }),
  )
}

export function useRaiseImpact(id: string) {
  return useAssessmentMutation(id, (impactId: string) =>
    api<AiImpact>(`/ai/systems/${id}/assessment/impacts/${impactId}/raise`, { method: "POST" }),
  )
}

export function useAssessmentAction(id: string) {
  return useAssessmentMutation(id, (action: "submit" | "approve" | "reopen") =>
    api<Assessment>(`/ai/systems/${id}/assessment/${action}`, { method: "POST" }),
  )
}
