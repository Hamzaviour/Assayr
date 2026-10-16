import { Link, useNavigate } from "@tanstack/react-router"
import { type CSSProperties, type FormEvent, useState } from "react"
import { DOC_TYPES, type DocType, type DocumentRow, useCreateDocument, useDocuments } from "../api/documents"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { Disclosure, DocStatus, ReviewDue } from "../components/DocumentSections"
import { formatDate } from "../lib/format"

const order = (i: number) => ({ "--i": i }) as CSSProperties

function nextCode(prefix: string, docs: DocumentRow[]): string {
  const numbers = docs
    .map((d) => d.code.match(new RegExp(`^${prefix}-(\\d+)$`))?.[1])
    .filter((n): n is string => !!n)
    .map(Number)
  return `${prefix}-${String(Math.max(0, ...numbers) + 1).padStart(2, "0")}`
}

function NewDocument({ docs, onClose }: { docs: DocumentRow[]; onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateDocument()
  const [type, setType] = useState<DocType>("policy")
  const prefixFor = (t: DocType) => DOC_TYPES.find((d) => d.type === t)!.prefix
  const [code, setCode] = useState(() => nextCode(prefixFor("policy"), docs))
  const [title, setTitle] = useState("")

  function onType(next: DocType) {
    setType(next)
    setCode(nextCode(prefixFor(next), docs))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate(
      { doc_type: type, code: code.trim(), title: title.trim() },
      { onSuccess: (doc) => navigate({ to: "/policies/$id", params: { id: doc.id } }) },
    )
  }

  const field = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
  return (
    <div role="dialog" aria-label="New document" className="rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <h2 className="mb-3 text-[15px] font-semibold">New document</h2>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-[160px_160px_minmax(0,1fr)] md:items-end">
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Type
          <select value={type} onChange={(e) => onType(e.target.value as DocType)} className={field}>
            {DOC_TYPES.map((d) => (
              <option key={d.type} value={d.type}>{d.singular[0].toUpperCase() + d.singular.slice(1)}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Reference
          <input value={code} onChange={(e) => setCode(e.target.value)} required maxLength={30} className={`${field} font-mono`} />
        </label>
        <label className="grid gap-1 text-[12.5px] text-fg-2">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={300} className={field} />
        </label>
        <div className="flex items-center gap-2 md:col-span-3">
          <Button type="submit" size="sm" disabled={create.isPending || !title.trim() || !code.trim()}>
            {create.isPending ? "Creating…" : "Create draft"}
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
        </div>
      </form>
    </div>
  )
}

function DocumentTable({ docs, label }: { docs: DocumentRow[]; label: string }) {
  if (docs.length === 0) return <p className="py-2 text-[13px] text-fg-3">No {label.toLowerCase()} yet.</p>
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
            <th className="px-4 py-2 font-medium">Ref</th>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Owner</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Version</th>
            <th className="px-4 py-2 font-medium">Next review</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id} className="border-t border-line hover:bg-subtle">
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12.5px] text-fg-2">{d.code}</td>
              <td className="min-w-56 px-4 py-2.5">
                <Link to="/policies/$id" params={{ id: d.id }} className="font-medium text-fg hover:text-primary">
                  {d.title}
                </Link>
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">{d.owner?.full_name ?? "Unassigned"}</td>
              <td className="px-4 py-2.5"><DocStatus status={d.status} /></td>
              <td className="px-4 py-2.5 tabular-nums text-fg-2">{d.version_label}</td>
              <td className="whitespace-nowrap px-4 py-2.5 text-fg-2">
                <span className="inline-flex items-center gap-2">
                  {d.review_due ? formatDate(d.review_due) : "—"}
                  {d.review_overdue && <ReviewDue />}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PoliciesPage() {
  const me = useMe()
  const documents = useDocuments()
  const [creating, setCreating] = useState(false)
  const [filter, setFilter] = useState("")
  const canCreate = (me.data?.permissions ?? []).includes("documents:create")
  const all = documents.data ?? []
  const term = filter.trim().toLowerCase()
  const shown = all.filter((d) => !term || d.title.toLowerCase().includes(term) || d.code.toLowerCase().includes(term))
  const overdue = all.filter((d) => d.review_overdue).length

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="rise flex flex-wrap items-end justify-between gap-3" style={order(0)}>
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Document register</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Policies, procedures and guidelines</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            {all.length} documents
            {overdue > 0 && <span className="font-semibold text-bad"> · {overdue} past their review date</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="document-search" className="sr-only">Search documents</label>
          <input
            id="document-search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by reference or title"
            className="w-60 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
          />
          {canCreate && !creating && <Button onClick={() => setCreating(true)}>New document</Button>}
        </div>
      </header>
      {creating && <NewDocument docs={all} onClose={() => setCreating(false)} />}
      {documents.isError && <p role="alert">{documents.error.message}</p>}
      {documents.isPending && <div className="h-40 animate-pulse rounded-xl bg-subtle" aria-label="Loading" />}
      {documents.isSuccess &&
        DOC_TYPES.map(({ type, label }, i) => {
          const docs = shown.filter((d) => d.doc_type === type)
          return (
            <div key={type} className="rise" style={order(i + 1)}>
              <Disclosure title={label} count={docs.length} defaultOpen={i === 0 || !!term}>
                <DocumentTable docs={docs} label={label} />
              </Disclosure>
            </div>
          )
        })}
    </div>
  )
}
