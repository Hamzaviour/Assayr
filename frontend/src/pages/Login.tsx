import { useRouter, useSearch } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { safeNext, useLogin } from "../auth/session"
import { Button } from "../components/Button"

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
    <main className="grid min-h-full place-items-center px-4 py-12">
      <form onSubmit={onSubmit} className="grid w-full max-w-sm gap-4 rounded-xl border border-line bg-surface p-6" noValidate>
        <div className="flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <span className="font-display text-xl font-extrabold tracking-tight">assayr</span>
        </div>
        <h1 className="font-display text-2xl font-extrabold tracking-tight">Sign in to Assayr</h1>
        {login.error && (
          <p role="alert" className="rounded-lg bg-bad-soft px-3 py-2 text-[13px] text-fg">
            {login.error.message}
          </p>
        )}
        <label className="grid gap-1 text-[13px] font-medium" htmlFor="login-email">
          Email
          <input id="login-email" type="email" autoComplete="username" required value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm font-normal" />
        </label>
        <label className="grid gap-1 text-[13px] font-medium" htmlFor="login-password">
          Password
          <input id="login-password" type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm font-normal" />
        </label>
        <Button type="submit" disabled={login.isPending} className="justify-center">
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  )
}
