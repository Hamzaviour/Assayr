import { Link, useNavigate } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useCreateRisk, useRiskLibrary } from "../api/risks"
import { Button } from "../components/Button"
import { OwnerPicker } from "../components/OwnerPicker"

export function RiskNewPage() {
  const library = useRiskLibrary()
  const create = useCreateRisk()
  const navigate = useNavigate()
  const [title, setTitle] = useState("")
  const [owner, setOwner] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const term = filter.trim().toLowerCase()
  const templates = (library.data?.templates ?? []).filter(
    (t) => !term || `${t.title} ${t.scenario} ${t.category}`.toLowerCase().includes(term),
  )

  async function start(body: { template_code?: string; title?: string }) {
    const risk = await create.mutateAsync(owner ? { ...body, owner_id: owner } : body)
    navigate({ to: "/risks/$code/assess", params: { code: risk.code } })
  }

  function onOwn(event: FormEvent) {
    event.preventDefault()
    if (title.trim()) void start({ title: title.trim() })
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span> New risk
      </nav>
      <header>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">New risk</h1>
        <p className="mt-1 text-[13.5px] text-fg-2">
          Start from one of {library.data?.templates.length ?? 0} ready-made scenarios, or describe your own.
        </p>
      </header>
      <form onSubmit={onOwn} className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface p-4">
        <div className="grid min-w-60 flex-1 gap-1">
          <label htmlFor="risk-title" className="text-[13px] font-medium">Your own scenario</label>
          <input id="risk-title" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Customer data leaked by a supplier" className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm" />
        </div>
        <div className="grid gap-1">
          <span className="text-[13px] font-medium">Owner</span>
          <OwnerPicker label="Risk owner" value={owner} onChange={setOwner} />
        </div>
        <Button type="submit" disabled={!title.trim() || create.isPending}>Start assessment</Button>
      </form>
      {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
      <section aria-labelledby="templates-heading" className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="templates-heading" className="text-[15px] font-semibold">Templates</h2>
          <input aria-label="Filter templates" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter templates"
            className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]" />
        </div>
        {library.isError && <p role="alert">{library.error.message}</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {templates.map((t) => (
            <li key={t.code} className="grid content-start gap-2 rounded-xl border border-line bg-surface p-4">
              <p className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{t.category}</p>
              <p className="font-semibold">{t.title}</p>
              <p className="text-[13px] text-fg-2">{t.scenario}</p>
              <div>
                <Button variant="secondary" size="sm" aria-label={`Use template: ${t.title}`} disabled={create.isPending}
                  onClick={() => void start({ template_code: t.code })}>
                  Use template
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
