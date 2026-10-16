import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

type Person = { id: string; full_name: string }

export const LAWFUL_BASIS: Record<string, string> = {
  consent: "Consent",
  contract: "Contract",
  legal_obligation: "Legal obligation",
  vital_interest: "Vital interest",
  public_interest: "Public interest",
  legitimate_interest: "Legitimate interest",
}
export const DATA_SUBJECTS: Record<string, string> = {
  employees: "Employees",
  customers: "Customers",
  suppliers: "Suppliers",
  visitors: "Visitors",
  children: "Children",
  patients: "Patients",
  students: "Students",
  public: "Members of the public",
  other: "Other",
}
export const ACTIVITY_STATUS: Record<string, string> = { draft: "Draft", active: "Active", retired: "Retired" }
export const privacyExportUrl = "/api/v1/privacy/export.xlsx"

export type ActivityInput = {
  name: string
  purpose: string | null
  data_subjects: string[]
  data_categories: string[]
  lawful_basis: string
  recipients: string | null
  cross_border: boolean
  transfer_countries: string | null
  retention: string | null
  security_measures: string | null
  owner_id: string | null
  status: string
  review_due: string | null
}

export type Activity = Omit<ActivityInput, "owner_id"> & {
  id: string
  code: string
  owner: Person | null
  sensitive: boolean
  review_overdue: boolean
  assets: { id: string; code: string; name: string; criticality_label: string }[]
  can_edit: boolean
}

export type InventoryRow = {
  id: string
  code: string
  name: string
  type: string
  owner: Person | null
  pii_categories: string[]
  pii_sensitive: boolean
  pii_volume: string | null
  criticality: number
  criticality_label: string
  activities: { code: string; name: string }[]
}

export type PrivacySummary = {
  pii_assets: number
  sensitive_assets: number
  activities: number
  active_activities: number
  cross_border: number
  reviews_due: number
}

export function usePrivacySummary() {
  return useQuery({ queryKey: ["privacy", "summary"], queryFn: () => api<PrivacySummary>("/privacy/summary") })
}

export function useActivities() {
  return useQuery({ queryKey: ["privacy", "activities"], queryFn: () => api<Activity[]>("/privacy/activities") })
}

export function useActivity(id: string) {
  return useQuery({ queryKey: ["privacy", "activity", id], queryFn: () => api<Activity>(`/privacy/activities/${id}`) })
}

export function useInventory() {
  return useQuery({ queryKey: ["privacy", "inventory"], queryFn: () => api<InventoryRow[]>("/privacy/inventory") })
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["privacy"] })
    queryClient.invalidateQueries({ queryKey: ["assets"] })
  }
}

export function useCreateActivity() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: ActivityInput) => api<Activity>("/privacy/activities", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: refresh,
  })
}

export function useUpdateActivity(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (changes: Partial<ActivityInput>) =>
      api<Activity>(`/privacy/activities/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: refresh,
  })
}

export function useLinkActivityAssets(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (asset_ids: string[]) =>
      api<Activity>(`/privacy/activities/${id}/assets`, { method: "PUT", body: JSON.stringify({ asset_ids }) }),
    onSuccess: refresh,
  })
}
