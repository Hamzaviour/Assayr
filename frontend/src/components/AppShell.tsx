import { useQueryClient } from "@tanstack/react-query"
import { Link, useRouter } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { isEmployeeOnly, type Me } from "../api/types"
import { useLogout } from "../auth/session"
import { toggleTheme } from "../lib/theme"
import { Button } from "./Button"
import { Icon } from "./icons"

type NavItem = {
  label: string
  icon: string
  to?: "/" | "/compliance" | "/controls" | "/evidence" | "/soa" | "/risks" | "/assets" | "/policies" | "/audits" | "/my-training" | "/users"
}
type NavSection = { group: string | null; items: NavItem[] }
const MY_TRAINING: NavItem = { label: "My training", icon: "training", to: "/my-training" }
const NAV: NavSection[] = [
  { group: null, items: [{ label: "Home", icon: "home", to: "/" }, MY_TRAINING] },
  {
    group: "Comply",
    items: [
      { label: "Compliance", icon: "soa", to: "/compliance" },
      { label: "Controls", icon: "controls", to: "/controls" },
      { label: "Evidence", icon: "evidence", to: "/evidence" },
      { label: "SoA", icon: "soa", to: "/soa" },
      { label: "Policies", icon: "policy", to: "/policies" },
    ],
  },
  { group: "Risk", items: [{ label: "Risks", icon: "risk", to: "/risks" }, { label: "Assets", icon: "asset", to: "/assets" }] },
  { group: "Assure", items: [{ label: "Audits", icon: "audit", to: "/audits" }] },
]

const itemClass =
  "relative flex items-center gap-2.5 rounded-lg px-2.5 py-[8px] font-medium transition-colors duration-200"

function navFor(me: Me): NavSection[] {
  if (isEmployeeOnly(me)) return [{ group: null, items: [MY_TRAINING] }]
  if (!me.permissions.includes("users:manage")) return NAV
  return [...NAV, { group: "Admin", items: [{ label: "Users", icon: "users", to: "/users" }] }]
}

export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  const logout = useLogout()
  const router = useRouter()
  const queryClient = useQueryClient()

  async function signOut() {
    await logout.mutateAsync()
    router.history.push("/login")
    queryClient.removeQueries({ queryKey: ["me"] })
  }

  return (
    <div className="grid h-full grid-cols-1 md:grid-cols-[236px_minmax(0,1fr)]">
      <nav aria-label="Main navigation" className="brand-rail hidden flex-col gap-1 px-3 py-4 text-on-brand-2 md:flex">
        <div className="flex items-center gap-2.5 px-2 pb-5">
          <img src="/favicon.svg" alt="" width={30} height={30} className="rounded-lg ring-1 ring-white/25" />
          <span className="font-display text-[22px] font-extrabold tracking-tight text-on-brand">assayr</span>
        </div>
        {navFor(me).map((section) => (
          <div key={section.group ?? "top"} className="grid gap-0.5">
            {section.group && (
              <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-semibold uppercase tracking-[0.1em] text-on-brand-3">
                {section.group}
              </p>
            )}
            {section.items.map((item) =>
              item.to ? (
                <Link
                  key={item.label}
                  to={item.to}
                  activeOptions={{ exact: item.to === "/" }}
                  className={`${itemClass} group text-on-brand-2 hover:bg-[var(--brand-hover)] hover:text-on-brand data-[status=active]:bg-[var(--brand-active)] data-[status=active]:text-on-brand`}
                >
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                  <span
                    aria-hidden="true"
                    className="ml-auto size-1.5 scale-0 rounded-full bg-gold transition-transform duration-300 group-data-[status=active]:scale-100"
                  />
                </Link>
              ) : (
                <span key={item.label} aria-disabled="true" className={`${itemClass} cursor-default text-on-brand-3`}>
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                  <span className="ml-auto rounded-full border border-white/20 px-1.5 text-[10px] font-medium">soon</span>
                </span>
              ),
            )}
          </div>
        ))}
        <p className="mt-auto flex items-center gap-2 border-t border-white/15 px-2.5 pt-3 text-xs text-on-brand-3">
          <Icon name="shield" size={15} />
          On-prem · no data leaves your network
        </p>
      </nav>
      <div className="flex min-w-0 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5 md:px-6">
          <span className="flex items-center gap-2 md:hidden">
            <img src="/favicon.svg" alt="" width={24} height={24} />
            <span className="font-display text-lg font-extrabold tracking-tight text-brand">assayr</span>
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => toggleTheme()} aria-label="Toggle light or dark theme">
              <Icon name="theme" />
            </Button>
            <span className="hidden text-[13px] text-fg-2 sm:inline">{me.full_name}</span>
            <Button variant="secondary" size="sm" onClick={signOut} disabled={logout.isPending}>
              <Icon name="logout" />
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-7">{children}</main>
      </div>
    </div>
  )
}
