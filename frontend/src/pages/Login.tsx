import { useRouter, useSearch } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { safeNext, useLogin } from "../auth/session"
import { Button } from "../components/Button"
import { Icon } from "../components/icons"

const PROMISES: [string, string, string][] = [
  ["server", "Runs on your own servers", "Evidence, risks and audit history never leave your network."],
  ["shield", "Every upload verified", "Malware-scanned and checked for dates, approvals and freshness, with the reasons shown."],
  ["offline", "No cloud, no telemetry", "Installs and runs without internet access, including air-gapped sites."],
]

const input =
  "rounded-lg border border-line-2 bg-surface px-3 py-2.5 text-sm font-normal transition-shadow duration-200 focus:border-primary focus:shadow-[0_0_0_3px_var(--primary-soft)] focus:outline-none"

export function LoginPage() {
  const { next } = useSearch({ from: "/login" })
  const router = useRouter()
  const login = useLogin()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await login.mutateAsync({ email, password })
      router.history.push(safeNext(next))
    } catch {
      /* the error is rendered from login.error */
    }
  }

  return (
    <main className="grid min-h-full bg-surface md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <section
        aria-label="About Assayr"
        className="brand-surface relative flex flex-col justify-between gap-10 overflow-hidden px-6 py-8 text-on-brand-2 md:px-14 md:py-12"
      >
        <div className="rise flex items-center gap-3" style={{ "--i": 0 } as React.CSSProperties}>
          <img src="/favicon.svg" alt="" width={44} height={44} className="rounded-xl ring-1 ring-white/30" />
          <span className="font-display text-[30px] font-extrabold tracking-tight text-on-brand">assayr</span>
        </div>
        <div className="grid max-w-xl gap-5">
          <p
            className="rise font-display text-[32px] font-extrabold leading-[1.1] tracking-[-0.02em] text-on-brand md:text-[44px]"
            style={{ "--i": 1 } as React.CSSProperties}
          >
            Proof, not paperwork.
          </p>
          <p className="rise max-w-md text-[15.5px] leading-relaxed" style={{ "--i": 2 } as React.CSSProperties}>
            Your ISO/IEC 27001 controls, evidence and risks in one place, verified automatically and kept on your own
            servers.
          </p>
          <ul className="mt-2 hidden gap-4 md:grid">
            {PROMISES.map(([icon, title, text], i) => (
              <li key={title} className="rise flex gap-3.5" style={{ "--i": 3 + i } as React.CSSProperties}>
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 text-on-brand ring-1 ring-white/15">
                  <Icon name={icon} size={18} />
                </span>
                <span>
                  <b className="block text-[14.5px] font-semibold text-on-brand">{title}</b>
                  <span className="text-[13.5px] text-on-brand-2">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="hidden text-[12.5px] text-on-brand-3 md:block">On-premise GRC for regulated organisations</p>
      </section>

      <section className="grid place-items-center px-5 py-12">
        <form onSubmit={onSubmit} className="rise grid w-full max-w-sm gap-5" style={{ "--i": 2 } as React.CSSProperties} noValidate>
          <div className="grid gap-1.5">
            <h1 className="font-display text-[28px] font-extrabold tracking-tight">Sign in to Assayr</h1>
            <p className="text-[14px] text-fg-2">Use the account your administrator created for you.</p>
          </div>
          {login.error && (
            <p role="alert" className="rounded-lg bg-bad-soft px-3 py-2 text-[13px] text-fg">
              {login.error.message}
            </p>
          )}
          <label className="grid gap-1.5 text-[13px] font-medium" htmlFor="login-email">
            Email
            <input id="login-email" type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} className={input} />
          </label>
          <label className="grid gap-1.5 text-[13px] font-medium" htmlFor="login-password">
            Password
            <input id="login-password" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} className={input} />
          </label>
          <Button type="submit" disabled={login.isPending} className="justify-center py-2.5">
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
          <p className="text-center text-[12.5px] text-fg-3">Forgotten your password? Ask your Assayr administrator.</p>
        </form>
      </section>
    </main>
  )
}
