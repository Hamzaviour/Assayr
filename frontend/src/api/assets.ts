import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Asset } from "./types"

export const ASSET_TYPE_LABEL: Record<string, string> = {
  information: "Information",
  application: "Application",
  server: "Server",
  endpoint: "Endpoint",
  network_device: "Network device",
  cloud_service: "Cloud service",
  facility: "Facility",
  people: "People / role",
  supplier_service: "Supplier service",
}
export const CLASSIFICATION_LABEL: Record<string, string> = {
  public: "Public", internal: "Internal", confidential: "Confidential", restricted: "Restricted",
}
export const LIFECYCLE_LABEL: Record<string, string> = { planned: "Planned", in_use: "In use", retired: "Retired" }

export interface AssetInput {
  name: string
  type: string
  owner_id?: string | null
  classification: string
  confidentiality: number
  integrity: number
  availability: number
  location: string | null
  description: string | null
  lifecycle: string
  holds_pii: boolean
  pii_categories: string[]
  pii_sensitive: boolean
  pii_volume: string | null
}

export type AssetFilters = { criticality?: number; pii?: boolean }

export function useAssets(includeRetired = false, filters: AssetFilters = {}) {
  return useQuery({
    queryKey: ["assets", includeRetired, filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (includeRetired) params.set("include_retired", "true")
      if (filters.criticality) params.set("criticality", String(filters.criticality))
      if (filters.pii) params.set("pii", "true")
      const query = params.toString()
      return api<Asset[]>(`/assets${query ? `?${query}` : ""}`)
    },
  })
}

export function useCreateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AssetInput) => api<Asset>("/assets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  })
}

export function useUpdateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...changes }: Partial<AssetInput> & { id: string }) =>
      api<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  })
}
