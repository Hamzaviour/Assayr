import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import {
  DOC_TYPES,
  type DocumentDetail,
  documentFileUrl,
  useApproveDocument,
  useDocument,
  useUpdateDocument,
  useUploadDocumentFile,
} from "../api/documents"
import { usePeople } from "../api/people"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { DocStatus, ReviewDue } from "../components/DocumentSections"
import { StatusPill } from "../components/StatusPill"
import { formatDate } from "../lib/format"

const CARD = "rounded-xl border border-line bg-surface p-5"
const LABEL = "mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3"

const ACTION: Record<string, string> = {
  "document.create": "Created",
  "document.update": "Details edited",
  "document.approve": "Approved",
  "document.file": "New file uploaded",
  "document.download": "Downloaded",
  "document.controls": "Linked controls changed",
  "document.link": "Linked to a control",
  "document.unlink": "Unlinked from a control",
}

const size = (bytes: number | null) =>
  bytes === null ? "" : bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

export function DocumentDetailPage() {
  const { id } = useParams({ from: "/app/policies/$id" })
  const document = useDocument(id)
  const me = useMe()
  const approve = useApproveDocument(id)
  const upload = useUploadDocumentFile(id)

  if (document.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (document.isError) return <p role="alert">{document.error.message}</p>
  const d = document.data
  const type = DOC_TYPES.find((t) => t.type === d.doc_type)
  const canUpload = d.status !== "retired" && (d.can_edit || d.can_approve || d.owner?.id === me.data?.id)

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/policies" className="hover:text-fg">{type?.label ?? "Documents"}</Link> <span aria-hidden="true">›</span>{" "}
        <span className="font-mono">{d.code}</span>
      </nav>
      <header className="rise relative flex flex-wrap items-start justify-between gap-4 overflow-hidden rounded-2xl border border-line bg-surface p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">
            {d.code} · {type?.singular ?? d.doc_type} · version {d.version_label}
          </p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{d.title}</h1>
          {d.description && <p className="mt-2 max-w-2xl text-[14px] text-fg-2">{d.description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {d.review_overdue && <ReviewDue />}
          <DocStatus status={d.status} />
          {d.can_approve && d.status === "draft" && (
            <Button size="sm" disabled={approve.isPending} onClick={() => approve.mutate()}>
              {approve.isPending ? "Approving…" : "Approve"}
            </Button>
          )}
        </div>
        {approve.isError && <p role="alert" className="w-full text-[13px] text-bad">{approve.error.message}</p>}
      </header>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid content-start gap-4">
          <section className={CARD} aria-labelledby="file-title">
            <h2 id="file-title" className={LABEL}>Current file</h2>
            {d.status === "draft" && d.approved_version && (
              <p className="mb-3 rounded-lg bg-ok-soft px-3 py-2 text-[13px] text-fg-2">
                Version {d.approved_version} stays in force until this draft is approved.{" "}
                {d.approved_filename && (
                  <a href={`${documentFileUrl(d.id)}?approved=true`} className="font-medium text-primary hover:underline">
                    Download approved {d.approved_filename}
                  </a>
                )}
              </p>
            )}
            {d.filename ? (
              <a href={documentFileUrl(d.id)} className="inline-flex items-center gap-2 font-medium text-primary hover:underline">
                Download {d.filename}
                <span className="text-[12.5px] font-normal text-fg-3">{size(d.size)}</span>
              </a>
            ) : (
              <p className="text-[13px] text-fg-3">No file uploaded yet.</p>
            )}
            {canUpload && (
              <div className="mt-4 grid gap-1 border-t border-line pt-4">
                <label htmlFor="document-file" className="text-[13px] font-medium">Upload a new file</label>
                <input
                  id="document-file"
                  type="file"
                  disabled={upload.isPending}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) upload.mutate(file)
                    e.target.value = ""
                  }}
                  className="text-[13px]"
                />
                {d.status === "approved" && (
                  <p className="text-[12.5px] text-fg-3">A new file starts the next version as a draft for approval.</p>
                )}
                {upload.isPending && <p role="status" className="text-[12.5px] text-fg-3">Uploading…</p>}
                {upload.isError && <p role="alert" className="text-[13px] text-bad">{upload.error.message}</p>}
              </div>
            )}
          </section>
          <section className={CARD} aria-label="Linked controls">
            <h2 className={LABEL}>Linked controls</h2>
            {d.controls.length === 0 ? (
              <p className="text-[13px] text-fg-3">Not linked to any control yet. Link it from a control page.</p>
            ) : (
              <ul className="grid gap-0.5">
                {d.controls.map((c) => (
                  <li key={c.code}>
                    <Link
                      to="/controls/$code"
                      params={{ code: c.code }}
                      className="flex items-center gap-3 rounded-md px-2 py-1.5 text-[13.5px] hover:bg-subtle"
                    >
                      <ControlId code={c.code} />
                      <span className="min-w-0 flex-1 truncate">{c.title}</span>
                      <StatusPill status={c.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <aside className="grid content-start gap-4">
          {(d.can_edit || d.can_approve) && <EditDetails d={d} />}
          <section className={CARD}>
            <h2 className={LABEL}>Details</h2>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
              <dt className="text-fg-3">Owner</dt>
              <dd>{d.owner?.full_name ?? "Unassigned"}</dd>
              <dt className="text-fg-3">Approved by</dt>
              <dd>{d.approved_by ? `${d.approved_by.full_name}${d.approved_at ? `, ${formatDate(d.approved_at)}` : ""}` : "Not approved"}</dd>
              <dt className="text-fg-3">Next review</dt>
              <dd>{d.review_due ? formatDate(d.review_due) : "—"}</dd>
            </dl>
          </section>
          <section className={CARD}>
            <h2 className={LABEL}>History</h2>
            <ol className="grid gap-2 text-[13px]">
              {d.history.map((h, i) => (
                <li key={i} className="grid">
                  <span>{ACTION[h.action] ?? h.action}</span>
                  <span className="text-[12px] text-fg-3">
                    {formatDate(h.at)}
                    {h.actor && ` · ${h.actor}`}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  )
}

function EditDetails({ d }: { d: DocumentDetail }) {
  const [open, setOpen] = useState(false)
  const update = useUpdateDocument(d.id)
  const people = usePeople()
  const [title, setTitle] = useState(d.title)
  const [code, setCode] = useState(d.code)
  const [description, setDescription] = useState(d.description ?? "")
  const [ownerId, setOwnerId] = useState(d.owner?.id ?? "")
  const [reviewDue, setReviewDue] = useState(d.review_due ?? "")
  const manager = d.can_approve
  const field = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] text-fg"

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: Parameters<typeof update.mutate>[0] = {}
    if (title.trim() !== d.title) changes.title = title.trim()
    if (code.trim().toUpperCase() !== d.code) changes.code = code.trim()
    if (description.trim() !== (d.description ?? "")) changes.description = description.trim() || null
    if (manager && ownerId !== (d.owner?.id ?? "")) changes.owner_id = ownerId || null
    if (manager && reviewDue !== (d.review_due ?? "")) changes.review_due = reviewDue || null
    update.mutate(changes, { onSuccess: () => setOpen(false) })
  }

  return (
    <section className={CARD}>
      <h2 className={LABEL}>Manage</h2>
      {!open ? (
        <div className="flex flex-wrap gap-2">
          {d.can_edit && (
            <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
              Edit details
            </Button>
          )}
          {manager && d.status !== "retired" && (
            <Button size="sm" variant="secondary" disabled={update.isPending} onClick={() => update.mutate({ status: "retired" })}>
              Retire document
            </Button>
          )}
        </div>
      ) : (
        <form onSubmit={onSubmit} className="grid gap-2.5">
          <label className="grid gap-1 text-[12.5px] text-fg-2">
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={300} className={field} />
          </label>
          <label className="grid gap-1 text-[12.5px] text-fg-2">
            Reference
            <input value={code} onChange={(e) => setCode(e.target.value)} required maxLength={30} className={`${field} font-mono`} />
          </label>
          <label className="grid gap-1 text-[12.5px] text-fg-2">
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={5000} className={field} />
          </label>
          {manager && (
            <>
              <label className="grid gap-1 text-[12.5px] text-fg-2">
                Owner
                <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)} className={field}>
                  <option value="">Unassigned</option>
                  {d.owner && !(people.data ?? []).some((p) => p.id === d.owner?.id) && (
                    <option value={d.owner.id}>{d.owner.full_name}</option>
                  )}
                  {(people.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>{p.full_name}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-[12.5px] text-fg-2">
                Next review
                <input type="date" value={reviewDue} onChange={(e) => setReviewDue(e.target.value)} className={field} />
              </label>
            </>
          )}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={update.isPending || !title.trim() || !code.trim()}>
              Save details
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {update.isError && <p role="alert" className="mt-2 text-[13px] text-bad">{update.error.message}</p>}
    </section>
  )
}
