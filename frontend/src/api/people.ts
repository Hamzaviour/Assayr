import { useQuery } from "@tanstack/react-query"
import { api } from "./client"
import type { Person } from "./types"

export function usePeople() {
  return useQuery({ queryKey: ["people"], queryFn: () => api<Person[]>("/people"), staleTime: 60_000 })
}
