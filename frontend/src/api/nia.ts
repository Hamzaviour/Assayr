import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export type NiaMapped = { code: string; title: string; status: string; coverage: "full" | "partial" }

export type NiaRow = {
  ref: string
  domain: string
  domain_name: string
  title: string
  status: string
  score: number | null
  applicable: boolean
  mandatory: boolean
  mapped: NiaMapped[]
}

export type NiaDetail = NiaRow & {
  summary: string | null
  text: string | null
  exclusion_reason: string | null
  can_edit: boolean
}

export type NiaLink = { code: string; coverage: "full" | "partial" }

const path = (ref: string) => `/nia/controls/${encodeURIComponent(ref)}`

/** NIA-only controls live in the ISO control table under this code. */
export const niaOnlyCode = (ref: string) => `NIA ${ref}`

export function useNiaControls() {
  return useQuery({ queryKey: ["nia", "controls"], queryFn: () => api<NiaRow[]>("/nia/controls") })
}

export function useNiaControl(ref: string) {
  return useQuery({ queryKey: ["nia", "control", ref], queryFn: () => api<NiaDetail>(path(ref)) })
}

function useNiaUpdate<T>(ref: string, send: (body: T) => Promise<NiaDetail>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (detail) => {
      queryClient.setQueryData(["nia", "control", ref], detail)
      queryClient.invalidateQueries({ queryKey: ["nia", "controls"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useSetNiaMapping(ref: string) {
  return useNiaUpdate(ref, (links: NiaLink[]) =>
    api<NiaDetail>(`${path(ref)}/mapping`, { method: "PUT", body: JSON.stringify({ links }) }),
  )
}

export function useSetNiaApplicability(ref: string) {
  return useNiaUpdate(ref, (body: { applicable: boolean; reason?: string }) =>
    api<NiaDetail>(`${path(ref)}/applicability`, { method: "POST", body: JSON.stringify(body) }),
  )
}
