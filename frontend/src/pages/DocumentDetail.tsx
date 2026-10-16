import { Link, useParams } from "@tanstack/react-router"
import { DOC_TYPES, documentFileUrl, useApproveDocument, useDocument, useUploadDocumentFile } from "../api/documents"
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
