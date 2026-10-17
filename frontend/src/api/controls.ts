import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { ControlDetail, ControlPage, ControlStats, RelatedControl } from "./types"

export type ControlFramework = "iso27001" | "iso42001" | "soc2"
export const FRAMEWORK_LABEL: Record<string, string> = {
  iso27001: "ISO/IEC 27001",
  nia: "NIA v2.1",
  iso42001: "ISO/IEC 42001",
  soc2: "SOC 2",
}

export const IMPLEMENTATION_LABEL: Record<string, string> = {
  not_started: "Not started",
  planned: "Planned",
  partial: "Partially implemented",
  implemented: "Implemented",
}

export function useControls(filters: {
  theme?: string
  q?: string
  owner?: string
  status?: string
  framework?: ControlFramework
  limit?: number
}) {
  return useInfiniteQuery({
    queryKey: ["controls", filters],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams()
      if (filters.theme) params.set("theme", filters.theme)
      if (filters.q) params.set("q", filters.q)
      if (filters.owner) params.set("owner", filters.owner)
      if (filters.status) params.set("status", filters.status)
      if (filters.framework && filters.framework !== "iso27001") params.set("framework", filters.framework)
      if (filters.limit) params.set("limit", String(filters.limit))
      if (pageParam !== undefined) params.set("cursor", String(pageParam))
      const query = params.toString()
      return api<ControlPage>(`/controls${query ? `?${query}` : ""}`)
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useControl(code: string) {
  return useQuery({
    queryKey: ["control", code],
    queryFn: () => api<ControlDetail>(`/controls/${encodeURIComponent(code)}`),
  })
}

export function useControlStats(framework: ControlFramework = "iso27001") {
  const query = framework === "iso27001" ? "" : `?framework=${framework}`
  return useQuery({
    queryKey: ["controls", "summary", framework],
    queryFn: () => api<ControlStats>(`/controls/summary${query}`),
  })
}

export function useRelated(code: string) {
  return useQuery({
    queryKey: ["control", code, "related"],
    queryFn: () => api<RelatedControl[]>(`/controls/${encodeURIComponent(code)}/related`),
  })
}

export function useReuseEvidence(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (versionId: string) =>
      api<ControlDetail>(`/controls/${encodeURIComponent(code)}/reuse-evidence`, {
        method: "POST",
        body: JSON.stringify({ version_id: versionId }),
      }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["control", code], detail)
      queryClient.invalidateQueries({ queryKey: ["control", code, "related"] })
    },
  })
}

export function useCreateActivity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { code: string; title: string; test_procedure?: string | null }) =>
      api<ControlDetail>("/soc2/activities", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["controls"] }),
  })
}

export function useUpdateActivity(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { title?: string; description?: string | null; test_procedure?: string | null }) =>
      api<ControlDetail>(`/soc2/activities/${encodeURIComponent(code)}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (detail) => queryClient.setQueryData(["control", code], detail),
  })
}

export function useUpdateControl(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (changes: { implementation_status?: string; implementation_text?: string | null }) =>
      api<ControlDetail>(`/controls/${encodeURIComponent(code)}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["control", code], detail)
      queryClient.invalidateQueries({ queryKey: ["controls"] })
    },
  })
}
