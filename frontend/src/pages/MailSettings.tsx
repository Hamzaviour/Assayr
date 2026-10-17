import { type FormEvent, useEffect, useState } from "react"
import { type MailSettings, type MailSettingsInput, useMailSettings, useSaveMailSettings, useSendTestEmail } from "../api/mail"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"

const CARD = "rounded-xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
const HOURS = Array.from({ length: 24 }, (_, h) => h)

const toInput = (s: MailSettings): MailSettingsInput => ({
  enabled: s.enabled,
  host: s.host ?? "",
  port: s.port,
  security: s.security,
  username: s.username ?? "",
  from_address: s.from_address ?? "",
  from_name: s.from_name ?? "",
  base_url: s.base_url ?? "",
  digest_hour: s.digest_hour,
})

export function MailSettingsPage() {
  const settings = useMailSettings()
  if (settings.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (settings.isError) return <p role="alert">{settings.error.message}</p>
  return <MailForm saved={settings.data} />
}

function MailForm({ saved }: { saved: MailSettings }) {
  const save = useSaveMailSettings()
  const test = useSendTestEmail()
  const [form, setForm] = useState<MailSettingsInput>(toInput(saved))
  const [changingPassword, setChangingPassword] = useState(!saved.password_set)
  const [password, setPassword] = useState("")
  useEffect(() => setChangingPassword(!saved.password_set), [saved.password_set])
  const set = (patch: Partial<MailSettingsInput>) => setForm({ ...form, ...patch })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const body: MailSettingsInput = { ...form }
    if (changingPassword && password) body.password = password
    save.mutate(body, { onSuccess: () => setPassword("") })
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-4">
      <header>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Admin</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Email</h1>
        <p className="mt-1 text-[13px] text-fg-2">
          Assayr sends each person one daily summary of what is overdue or due soon, through your own mail server. This is its
          only outbound connection, and it stays off until you turn it on.
        </p>
      </header>

      {!saved.key_configured && (
        <p role="alert" className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-[13px]">
          This server has no ASSAYR_SECRET_KEY, so a mail password can not be saved. Run the newer installer (it adds one), or add
          ASSAYR_SECRET_KEY to assayr.env and restart Assayr.
        </p>
      )}

      <form onSubmit={onSubmit} className={`${CARD} grid gap-4 md:grid-cols-2`} aria-label="Mail server settings">
        <label className="flex items-center gap-2 text-[14px] font-semibold md:col-span-2">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
          Send the daily summary email
        </label>
        <label className={LABEL}>
          Mail server
          <input value={form.host ?? ""} onChange={(e) => set({ host: e.target.value })} placeholder="mail.example.local" maxLength={255} className={FIELD} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className={LABEL}>
            Port
            <input type="number" min={1} max={65535} value={form.port} onChange={(e) => set({ port: Number(e.target.value) })} className={FIELD} />
          </label>
          <label className={LABEL}>
            Security
            <select value={form.security} onChange={(e) => set({ security: e.target.value as MailSettings["security"] })} className={FIELD}>
              <option value="starttls">STARTTLS (usually 587)</option>
              <option value="ssl">SSL/TLS (usually 465)</option>
              <option value="none">None (usually 25)</option>
            </select>
          </label>
        </div>
        <label className={LABEL}>
          User name
          <input value={form.username ?? ""} onChange={(e) => set({ username: e.target.value })} placeholder="Leave empty if the server needs no sign-in" maxLength={255} autoComplete="off" className={FIELD} />
        </label>
        <div className={LABEL}>
          {changingPassword ? (
            <label className={LABEL}>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} maxLength={500} autoComplete="new-password" className={FIELD} />
            </label>
          ) : (
            <>
              <span>Password</span>
              <span className="flex items-center gap-2 text-[13px] font-normal text-fg-2">
                A password is saved.
                <Button type="button" size="sm" variant="secondary" onClick={() => setChangingPassword(true)}>Change password</Button>
              </span>
            </>
          )}
        </div>
        <label className={LABEL}>
          From address
          <input value={form.from_address ?? ""} onChange={(e) => set({ from_address: e.target.value })} placeholder="assayr@example.com" maxLength={320} className={FIELD} />
        </label>
        <label className={LABEL}>
          From name
          <input value={form.from_name ?? ""} onChange={(e) => set({ from_name: e.target.value })} placeholder="Assayr" maxLength={200} className={FIELD} />
        </label>
        <label className={LABEL}>
          Assayr address
          <input value={form.base_url ?? ""} onChange={(e) => set({ base_url: e.target.value })} placeholder="https://grc.example.local" maxLength={500} className={FIELD} />
          <span className="font-normal text-fg-3">Links in the email open this address.</span>
        </label>
        <label className={LABEL}>
          Send at
          <select value={form.digest_hour} onChange={(e) => set({ digest_hour: Number(e.target.value) })} className={FIELD}>
            {HOURS.map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
          </select>
          <span className="font-normal text-fg-3">Server time, every day.</span>
        </label>
        <div className="flex flex-wrap items-center gap-2 md:col-span-2">
          <Button type="submit" size="sm" disabled={save.isPending}>Save</Button>
          <Button type="button" size="sm" variant="secondary" disabled={test.isPending || !saved.host} onClick={() => test.mutate()}>
            Send test email
          </Button>
          {save.isSuccess && !save.isPending && <span role="status" className="text-[13px] text-ok">Saved.</span>}
          {test.isSuccess && <span role="status" className="text-[13px] text-ok">Test email sent to {test.data.sent_to}.</span>}
          {save.isError && <p role="alert" className="text-[13px] text-bad">{save.error.message}</p>}
          {test.isError && <p role="alert" className="text-[13px] text-bad">{test.error.message}</p>}
        </div>
      </form>

      <section className={CARD} aria-label="Last daily summary">
        <h2 className="text-[15px] font-semibold">Last daily summary</h2>
        {saved.last_run ? (
          <div className="mt-2 grid gap-1 text-[13px]">
            <p>
              {formatDate(saved.last_run.day)}: sent to {saved.last_run.sent} {saved.last_run.sent === 1 ? "person" : "people"}
              {saved.last_run.status === "failed" && <span className="font-semibold text-bad"> · the mail server could not be used</span>}
            </p>
            {saved.last_run.error && <p className="text-bad">{saved.last_run.error}</p>}
          </div>
        ) : (
          <p className="mt-2 text-[13px] text-fg-3">Not sent yet.</p>
        )}
      </section>
    </div>
  )
}
