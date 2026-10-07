import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import type { Me } from "../api/types"

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), retry: false, staleTime: 60_000 })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api<Me>("/auth/login", { method: "POST", body: JSON.stringify(credentials) }),
    onSuccess: (me) => queryClient.setQueryData(["me"], me),
  })
}

export function useLogout() {
  return useMutation({ mutationFn: () => api<void>("/auth/logout", { method: "POST" }) })
}

/** Only allow same-site relative paths after sign-in; anything else goes home. */
export function safeNext(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/"
  if (next === "/login" || next.startsWith("/login?")) return "/"
  return next
}
