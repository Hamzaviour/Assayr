import { useState } from "react"
import { type ImportResult, useImportUsers, useUsers } from "../api/users"
import { Button } from "../components/Button"

const ROLE_LABEL: Record<string, string> = {
  platform_admin: "Platform admin",
  isms_manager: "ISMS manager",
  control_owner: "Control owner",
  risk_owner: "Risk owner",
  contributor: "Contributor",
  internal_auditor: "Internal auditor",
  external_auditor: "External auditor",
  executive: "Executive",
  employee: "Employee",
  privacy_officer: "Privacy officer",
  viewer: "Viewer",
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ""))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

function countRows(text: string): number {
  return Math.max(0, text.split(/\r?\n/).filter((line) => line.trim()).length - 1)
}

function Created({ result }: { result: ImportResult }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    const text = result.created.map((c) => `${c.full_name}\t${c.email}\t${c.temporary_password}`).join("\n")
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="grid gap-2">
      <p className="rounded-lg bg-warn-soft px-3 py-2 text-[12.5px] text-fg">
        Temporary passwords are shown only once. Hand each person theirs privately; they choose their own at first sign-in.
      </p>
      <table aria-label="Accounts created" className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-fg-3">
            <th className="py-1.5 pr-3 font-medium">Name</th>
            <th className="py-1.5 pr-3 font-medium">Email</th>
            <th className="py-1.5 pr-3 font-medium">Temporary password</th>
            <th className="py-1.5 text-right">
              <Button size="sm" variant="secondary" onClick={copy}>{copied ? "Copied" : "Copy all"}</Button>
            </th>
          </tr>
        </thead>
        <tbody>
          {result.created.map((c) => (
            <tr key={c.email} className="border-t border-line">
              <td className="py-1.5 pr-3">{c.full_name}</td>
              <td className="py-1.5 pr-3 text-fg-2">{c.email}</td>
              <td className="py-1.5 pr-3 font-mono text-[12.5px]" colSpan={2}>{c.temporary_password}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ImportPanel({ onClose }: { onClose: () => void }) {
  const importUsers = useImportUsers()
  const [file, setFile] = useState<File | null>(null)
  const [rows, setRows] = useState(0)
  const result = importUsers.data

  return (
    <div role="dialog" aria-label="Import staff from CSV" className="rise relative grid gap-3 overflow-hidden rounded-2xl border border-line bg-surface p-5">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <h2 className="text-[15px] font-semibold">Import staff from CSV</h2>
      <p className="text-[12.5px] text-fg-3">
        Columns: <code>name</code>, <code>email</code>, <code>department</code> (optional), <code>role</code> (optional, Employee by default).
        Excel's "CSV UTF-8" works, with commas or semicolons.
      </p>
      <label className="grid gap-1 text-[12.5px] text-fg-2">
        Staff list (.csv)
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={async (e) => {
            const chosen = e.target.files?.[0] ?? null
            setFile(chosen)
            setRows(chosen ? countRows(await readText(chosen)) : 0)
          }}
          className="text-[13px] text-fg"
        />
      </label>
      {file && <p className="text-[13px] font-medium">{rows} people in this file</p>}
      <div className="flex gap-2">
        <Button size="sm" disabled={!file || importUsers.isPending} onClick={() => file && importUsers.mutate(file)}>
          {importUsers.isPending ? "Creating…" : "Create accounts"}
        </Button>
        <Button size="sm" variant="secondary" onClick={onClose}>Close</Button>
      </div>
      {importUsers.isError && <p role="alert" className="text-[13px] text-bad">{importUsers.error.message}</p>}
      {result && result.created.length > 0 && <Created result={result} />}
      {result && result.created.length === 0 && <p className="text-[13px] text-fg-2">No new accounts were created.</p>}
      {result && result.skipped.length > 0 && (
        <ul className="grid gap-0.5 text-[12.5px] text-warn">
          {result.skipped.map((s) => (
            <li key={`${s.line}-${s.email}`}>
              Line {s.line}: {s.email ?? "—"} — {s.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function UsersPage() {
  const users = useUsers()
  const [importing, setImporting] = useState(false)
  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="rise flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Admin</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Users</h1>
        </div>
        {!importing && <Button onClick={() => setImporting(true)}>Import CSV</Button>}
      </header>
      {importing && <ImportPanel onClose={() => setImporting(false)} />}
      {users.isError && <p role="alert">{users.error.message}</p>}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Department</th>
              <th className="px-4 py-3 font-medium">Roles</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((u) => (
              <tr key={u.id} className="border-t border-line">
                <td className="px-4 py-2.5 font-medium">{u.full_name}</td>
                <td className="px-4 py-2.5 text-fg-2">{u.email}</td>
                <td className="px-4 py-2.5 text-fg-2">{u.department ?? "—"}</td>
                <td className="px-4 py-2.5">
                  <span className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <span key={`${r.role}-${r.scope_id}`} className="rounded-full bg-primary-soft px-2 py-0.5 text-[11.5px] font-semibold text-primary">
                        {ROLE_LABEL[r.role] ?? r.role}
                      </span>
                    ))}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-[12.5px]">
                  {!u.is_active ? (
                    <span className="text-fg-3">Deactivated</span>
                  ) : u.must_change_password ? (
                    <span className="text-warn">Waiting for first sign-in</span>
                  ) : (
                    <span className="text-ok">Active</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
