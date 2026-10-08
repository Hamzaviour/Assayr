import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { ArtefactLink, ControlDetail, Readiness, ReviewItem } from "./types"

export function uploadEvidence(code: string, slotId: string, file: File): Promise<ArtefactLink> {
  const form = new FormData()
  form.set("file", file)
  return api<ArtefactLink>(`/controls/${encodeURIComponent(code)}/slots/${slotId}/artefacts`, {
    method: "POST",
    body: form,
  })
}

export function useUploadEvidence(code: string) {
  return useMutation({ mutationFn: ({ slotId, file }: { slotId: string; file: File }) => uploadEvidence(code, slotId, file) })
}

export function useLink(linkId: string) {
  return useQuery({
    queryKey: ["link", linkId],
    queryFn: () => api<ArtefactLink>(`/artefact-links/${linkId}`),
    refetchInterval: (query) => (query.state.data?.state === "verifying" ? 800 : false),
  })
}

export function useReviewQueue() {
  return useQuery({ queryKey: ["review-queue"], queryFn: () => api<ReviewItem[]>("/review-queue") })
}

export function useDecision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ linkId, decision, reason }: { linkId: string; decision: "accept" | "reject"; reason: string }) =>
      api<ArtefactLink>(`/artefact-links/${linkId}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, reason: reason.trim() || null }),
      }),
    onSuccess: (link) => {
      queryClient.setQueryData(["link", link.id], link)
      queryClient.invalidateQueries({ queryKey: ["review-queue"] })
      queryClient.invalidateQueries({ queryKey: ["control", link.control_code] })
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useAttest(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (statement: string) =>
      api<ControlDetail>(`/controls/${encodeURIComponent(code)}/attest`, {
        method: "POST",
        body: JSON.stringify({ statement }),
      }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["control", code], detail)
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useReadiness() {
  return useQuery({ queryKey: ["readiness"], queryFn: () => api<Readiness>("/readiness") })
}
