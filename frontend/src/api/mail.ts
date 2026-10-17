import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export interface MailSettings {
  enabled: boolean
  host: string | null
  port: number
  security: "starttls" | "ssl" | "none"
  username: string | null
  password_set: boolean
  from_address: string | null
  from_name: string | null
  base_url: string | null
  digest_hour: number
  key_configured: boolean
  last_run: { day: string; status: string; sent: number; error: string | null } | null
}

export type MailSettingsInput = Omit<MailSettings, "password_set" | "key_configured" | "last_run"> & { password?: string }

export function useMailSettings() {
  return useQuery({ queryKey: ["mail-settings"], queryFn: () => api<MailSettings>("/settings/mail") })
}

export function useSaveMailSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MailSettingsInput) => api<MailSettings>("/settings/mail", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (saved) => queryClient.setQueryData(["mail-settings"], saved),
  })
}

export function useSendTestEmail() {
  return useMutation({ mutationFn: () => api<{ sent_to: string }>("/settings/mail/test", { method: "POST" }) })
}

export function useDigestOptOut() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (optOut: boolean) =>
      api<{ digest_opt_out: boolean }>("/me/digest", { method: "PATCH", body: JSON.stringify({ opt_out: optOut }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  })
}
