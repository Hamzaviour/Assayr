import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Me } from "./types"

export type UserRow = Me
export type ImportResult = {
  created: { email: string; full_name: string; temporary_password: string }[]
  skipped: { line: number; email: string | null; reason: string }[]
}

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: () => api<UserRow[]>("/users") })
}

export function useImportUsers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append("file", file)
      return api<ImportResult>("/users/import", { method: "POST", body: form })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
      queryClient.invalidateQueries({ queryKey: ["people"] })
    },
  })
}
