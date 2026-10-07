import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { ControlDetail, ControlPage, ControlStats } from "./types"

export const IMPLEMENTATION_LABEL: Record<string, string> = {
  not_started: "Not started",
  planned: "Planned",
  partial: "Partially implemented",
  implemented: "Implemented",
}

export function useControls(filters: { theme?: string; q?: string }) {
  return useInfiniteQuery({
    queryKey: ["controls", filters],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams()
      if (filters.theme) params.set("theme", filters.theme)
      if (filters.q) params.set("q", filters.q)
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

export function useControlStats() {
  return useQuery({ queryKey: ["controls", "summary"], queryFn: () => api<ControlStats>("/controls/summary") })
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
