import { useMutation, useQueryClient } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"
import { api } from "../api/client"
import { Button } from "../components/Button"

const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-3 py-2 text-[14px] text-fg"

/** Shown instead of the app until a temporary password (from a staff import) is replaced. */
export function ChangePasswordPage() {
  const queryClient = useQueryClient()
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const change = useMutation({
    mutationFn: () =>
      api<void>("/auth/password", { method: "POST", body: JSON.stringify({ current_password: current, new_password: next }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  })
  const mismatch = confirm.length > 0 && confirm !== next

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    change.mutate()
  }

  return (
    <main className="grid min-h-full place-items-center bg-canvas p-6">
      <div className="rise relative w-full max-w-md overflow-hidden rounded-2xl border border-line bg-surface p-8 shadow-sm">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
        <img src="/favicon.svg" alt="" width={40} height={40} className="mb-4 rounded-xl" />
        <h1 className="font-display text-[24px] font-extrabold tracking-tight">Choose a new password</h1>
        <p className="mt-1 text-[13.5px] text-fg-2">
          You signed in with a temporary password. Choose your own to continue. Use at least 12 characters.
        </p>
        <form onSubmit={onSubmit} className="mt-5 grid gap-3">
          <label className="grid gap-1 text-[13px] font-medium">
            Temporary password
            <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className={FIELD} required />
          </label>
          <label className="grid gap-1 text-[13px] font-medium">
            New password
            <input type="password" autoComplete="new-password" minLength={12} value={next} onChange={(e) => setNext(e.target.value)} className={FIELD} required />
          </label>
          <label className="grid gap-1 text-[13px] font-medium">
            Confirm new password
            <input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={FIELD} required />
          </label>
          {mismatch && <p className="text-[12.5px] text-bad">The two new passwords don't match.</p>}
          {change.isError && <p role="alert" className="text-[13px] text-bad">{change.error.message}</p>}
          <Button type="submit" disabled={!current || next.length < 12 || mismatch || confirm !== next || change.isPending}>
            {change.isPending ? "Saving…" : "Save new password"}
          </Button>
        </form>
      </div>
    </main>
  )
}
