import { useState } from "react"
import type { Activity } from "../../api/privacy"
import { useLinkActivityProcessors, useProcessors } from "../../api/privacy2"
import { Button } from "../../components/Button"

export function ActivityProcessors({ activity }: { activity: Activity }) {
  const processors = useProcessors()
  const link = useLinkActivityProcessors(activity.id)
  const [chosen, setChosen] = useState<string[]>((activity.processors ?? []).map((p) => p.id))
  const all = (processors.data ?? []).filter((p) => p.status === "active" || chosen.includes(p.id))

  return (
    <section aria-label="Processors" className="grid gap-3 rounded-2xl border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold">Processors</h2>
      <p className="text-[12.5px] text-fg-3">Vendors that handle this personal data on your behalf.</p>
      {processors.isSuccess && all.length === 0 && (
        <p className="text-[13px] text-fg-3">No processors yet. Add them on the Processors tab.</p>
      )}
      <ul className="grid gap-1.5 md:grid-cols-2">
        {all.map((p) => (
          <li key={p.id}>
            <label className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
              <input
                type="checkbox"
                disabled={!activity.can_edit}
                checked={chosen.includes(p.id)}
                onChange={(e) => setChosen(e.target.checked ? [...chosen, p.id] : chosen.filter((x) => x !== p.id))}
              />
              <span className="flex-1">{p.name}</span>
              {!p.dpa_signed && <span className="rounded-full bg-bad-soft px-2 py-0.5 text-[11px] font-semibold text-bad">No agreement</span>}
            </label>
          </li>
        ))}
      </ul>
      {activity.can_edit && (
        <div className="flex items-center gap-3">
          <Button size="sm" disabled={link.isPending} onClick={() => link.mutate(chosen)}>Save processors</Button>
          {link.isError && <p role="alert" className="text-[13px] text-bad">{link.error.message}</p>}
        </div>
      )}
    </section>
  )
}
