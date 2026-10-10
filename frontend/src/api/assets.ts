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
}

export function useAssets(includeRetired = false) {
  return useQuery({
    queryKey: ["assets", includeRetired],
    queryFn: () => api<Asset[]>(`/assets${includeRetired ? "?include_retired=true" : ""}`),
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
