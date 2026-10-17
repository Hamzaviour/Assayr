import { Link } from "@tanstack/react-router"
import { type ReactNode, useId, useState } from "react"
import {
  type ControlDocument,
  DOC_TYPES,
  type DocType,
  useControlDocuments,
  useDocuments,
  useLinkControlDocument,
} from "../api/documents"
import { Status } from "./Status"

export function DocStatus({ status }: { status: string }) {
  return <Status area="document" value={status} />
}

export function ReviewDue() {
  return <span className="whitespace-nowrap rounded-full bg-bad-soft px-2 py-0.5 text-[11.5px] font-semibold text-bad">Review due</span>
}

/** An accessible disclosure: a button with aria-expanded that shows or hides a labelled region. */
export function Disclosure({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string
  count: number
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return (
    <div className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors duration-200 hover:bg-subtle"
      >
        <span className="text-[14.5px] font-semibold">{title}</span>
        <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[12px] font-semibold tabular-nums text-primary">{count}</span>
        <svg aria-hidden="true" viewBox="0 0 16 16" className={`ml-auto h-4 w-4 text-fg-3 transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div id={id} role="region" aria-label={title} className="border-t border-line px-4 py-3">
          {children}
        </div>
      )}
    </div>
  )
}

function Picker({ type, singular, linked, code }: { type: DocType; singular: string; linked: ControlDocument[]; code: string }) {
  const [open, setOpen] = useState(false)
  const [term, setTerm] = useState("")
  const documents = useDocuments()
  const link = useLinkControlDocument(code)
  const linkedIds = new Set(linked.map((d) => d.id))
  const q = term.trim().toLowerCase()
  const candidates = (documents.data ?? []).filter(
    (d) =>
      d.doc_type === type &&
      d.status !== "retired" &&
      !linkedIds.has(d.id) &&
      (!q || d.title.toLowerCase().includes(q) || d.code.toLowerCase().includes(q)),
  )
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-2 text-[13px] font-semibold text-primary hover:underline">
        Link a document
      </button>
    )
  }
  const inputId = `${code}-${type}-find`
  return (
    <div className="mt-3 grid gap-2 rounded-lg border border-line bg-subtle p-3">
      <label htmlFor={inputId} className="text-[12.5px] text-fg-2">Find a {singular}</label>
      <input
        id={inputId}
        autoFocus
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="Reference or title"
        className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]"
      />
      {documents.isPending && <p className="text-[12.5px] text-fg-3">Loading…</p>}
      <ul role="listbox" aria-label={`${singular} documents`} className="grid max-h-56 gap-0.5 overflow-y-auto">
        {candidates.map((d) => (
          <li key={d.id}>
            <button
              type="button"
              role="option"
              aria-selected={false}
              disabled={link.isPending}
              onClick={() => link.mutate({ id: d.id, link: true }, { onSuccess: () => setOpen(false) })}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-surface"
            >
              <span className="font-mono text-[12px] text-fg-3">{d.code}</span>
              <span className="min-w-0 flex-1 truncate">{d.title}</span>
              <DocStatus status={d.status} />
            </button>
          </li>
        ))}
      </ul>
      {documents.isSuccess && candidates.length === 0 && (
        <p className="text-[12.5px] text-fg-3">
          No other {singular} documents. <Link to="/policies" className="text-primary hover:underline">Add one on the Policies page</Link>.
        </p>
      )}
      {link.isError && <p role="alert" className="text-[12.5px] text-bad">{link.error.message}</p>}
      <button type="button" onClick={() => setOpen(false)} className="justify-self-start text-[12.5px] text-fg-3 hover:text-fg">
        Cancel
      </button>
    </div>
  )
}

function Unlink({ code, doc }: { code: string; doc: ControlDocument }) {
  const link = useLinkControlDocument(code)
  return (
    <button
      type="button"
      aria-label={`Unlink ${doc.code}`}
      title="Unlink from this control"
      disabled={link.isPending}
      onClick={() => link.mutate({ id: doc.id, link: false })}
      className="rounded px-2 py-1 text-fg-3 transition-colors hover:bg-subtle hover:text-bad"
    >
      ×
    </button>
  )
}

/**
 * Policies, procedures and guidelines linked to one or more controls.
 * `linkTo` is the control that "Link a document" adds to; without it the sections are read-only.
 */
export function DocumentSections({ codes, linkTo, canLink, hint }: { codes: string[]; linkTo?: string; canLink: boolean; hint?: string }) {
  const docs = useControlDocuments(codes)
  return (
    <section aria-labelledby="documents-title" className="grid gap-2">
      <h2 id="documents-title" className="text-[15px] font-semibold">Policies, procedures and guidelines</h2>
      {hint && <p className="text-[12.5px] text-fg-3">{hint}</p>}
      {docs.error && <p role="alert" className="text-[13px] text-bad">{docs.error.message}</p>}
      {DOC_TYPES.map(({ type, label, singular }) => {
        const list = docs.data[type]
        return (
          <Disclosure key={type} title={label} count={list.length}>
            {list.length === 0 ? (
              <p className="text-[13px] text-fg-3">No {label.toLowerCase()} linked yet</p>
            ) : (
              <ul className="grid gap-0.5">
                {list.map((d) => (
                  <li key={d.id} className="flex items-center gap-1">
                    <Link
                      to="/policies/$id"
                      params={{ id: d.id }}
                      className="flex min-w-0 flex-1 flex-wrap items-center gap-2 rounded-md px-2 py-1.5 text-[13.5px] hover:bg-subtle"
                    >
                      <span className="font-mono text-[12px] text-fg-3">{d.code}</span>
                      <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
                      <span className="text-[12px] text-fg-3">
                        v{d.version_label}
                        {d.status === "draft" && d.approved_version && ` · v${d.approved_version} in force`}
                      </span>
                      {d.review_overdue && <ReviewDue />}
                      <DocStatus status={d.status} />
                    </Link>
                    {canLink && linkTo && <Unlink code={linkTo} doc={d} />}
                  </li>
                ))}
              </ul>
            )}
            {canLink && linkTo && <Picker type={type} singular={singular} linked={list} code={linkTo} />}
          </Disclosure>
        )
      })}
    </section>
  )
}
