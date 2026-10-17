import { useEffect, useId, useRef, useState } from "react"
import type { Me } from "../api/types"
import { useDigestOptOut } from "../api/mail"

/** The person's name in the top bar; opens their own settings (the daily summary email). */
export function UserMenu({ me }: { me: Me }) {
  const [open, setOpen] = useState(false)
  const digest = useDigestOptOut()
  const panelId = useId()
  const ref = useRef<HTMLDivElement>(null)
  const optedOut = digest.data?.digest_opt_out ?? me.digest_opt_out ?? false

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", close)
    document.addEventListener("keydown", close)
    return () => {
      document.removeEventListener("mousedown", close)
      document.removeEventListener("keydown", close)
    }
  }, [open])

  return (
    <div ref={ref} className="relative hidden sm:block">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="rounded-lg px-2 py-1 text-[13px] text-fg-2 hover:bg-subtle hover:text-fg"
      >
        {me.full_name}
      </button>
      {open && (
        <div id={panelId} className="absolute right-0 z-20 mt-1 w-72 rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-lift)]">
          <p className="text-[13px] font-semibold">{me.full_name}</p>
          <p className="text-[12px] text-fg-3">{me.email}</p>
          <label className="mt-3 flex items-start gap-2 text-[13px]">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={!optedOut}
              disabled={digest.isPending}
              aria-describedby={`${panelId}-hint`}
              onChange={(e) => digest.mutate(!e.target.checked)}
            />
            Email me a daily summary
          </label>
          <p id={`${panelId}-hint`} className="ml-6 text-[12px] text-fg-3">
            What is overdue or due soon for you, once a day, when email is set up.
          </p>
          {digest.isError && <p role="alert" className="mt-2 text-[12px] text-bad">{digest.error.message}</p>}
        </div>
      )}
    </div>
  )
}
