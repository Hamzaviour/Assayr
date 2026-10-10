import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Soa, SoaVersion } from "./types"

export const SOURCE_LABEL: Record<string, string> = {
  legal: "Legal or regulatory",
  contractual: "Contractual",
  business: "Business requirement",
  best_practice: "Best practice",
}

export function useSoa() {
  return useQuery({ queryKey: ["soa"], queryFn: () => api<Soa>("/soa") })
}

export function useSoaVersions() {
  return useQuery({ queryKey: ["soa-versions"], queryFn: () => api<SoaVersion[]>("/soa/versions") })
}

export function useUpdateSoaItems() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      codes: string[]
      applicable?: boolean
      sources?: string[]
      justification?: string | null
      exclusion_reason?: string | null
    }) => api<Soa>("/soa/items", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (soa) => {
      queryClient.setQueryData(["soa"], soa)
      queryClient.invalidateQueries({ queryKey: ["controls"] })
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useSubmitSoa() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (_body: void) => api<SoaVersion>("/soa/versions", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soa-versions"] }),
  })
}

export function useDecideSoa() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ version, decision, reason }: { version: number; decision: "approve" | "return"; reason?: string }) =>
      api<SoaVersion>(`/soa/versions/${version}/${decision}`, {
        method: "POST",
        body: decision === "return" ? JSON.stringify({ reason }) : undefined,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soa-versions"] }),
  })
}
