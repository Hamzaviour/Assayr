import { useQueryClient } from "@tanstack/react-query"
import { Link, useRouter } from "@tanstack/react-router"
import type { ReactNode } from "react"
import type { Me } from "../api/types"
import { useLogout } from "../auth/session"
import { toggleTheme } from "../lib/theme"
import { Button } from "./Button"
import { Icon } from "./icons"

type NavItem = { label: string; icon: string; to?: "/" | "/controls" | "/evidence" | "/risks" }
const NAV: { group: string | null; items: NavItem[] }[] = [
  { group: null, items: [{ label: "Home", icon: "home", to: "/" }] },
  {
    group: "Comply",
    items: [
      { label: "Controls", icon: "controls", to: "/controls" },
      { label: "Evidence", icon: "evidence", to: "/evidence" },
      { label: "SoA", icon: "soa" },
      { label: "Policies", icon: "policy" },
    ],
  },
  { group: "Risk", items: [{ label: "Risks", icon: "risk", to: "/risks" }] },
  { group: "Assure", items: [{ label: "Audits", icon: "audit" }] },
]

const itemClass = "flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] font-medium"

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
      <nav aria-label="Main navigation" className="hidden flex-col gap-1 border-r border-line bg-surface px-3 py-4 md:flex">
        <div className="flex items-center gap-2.5 px-2 pb-4">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span className="font-display text-[21px] font-extrabold tracking-tight">assayr</span>
        </div>
        {NAV.map((section) => (
          <div key={section.group ?? "top"} className="grid gap-0.5">
            {section.group && (
              <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">
                {section.group}
              </p>
            )}
            {section.items.map((item) =>
              item.to ? (
                <Link
                  key={item.label}
                  to={item.to}
                  activeOptions={{ exact: item.to === "/" }}
                  className={`${itemClass} text-fg-2 hover:bg-subtle hover:text-fg data-[status=active]:bg-primary-soft data-[status=active]:text-primary`}
                >
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                </Link>
              ) : (
                <span key={item.label} aria-disabled="true" className={`${itemClass} cursor-default text-fg-3`}>
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                  <span className="ml-auto font-mono text-[10px]">soon</span>
                </span>
              ),
            )}
          </div>
        ))}
        <p className="mt-auto border-t border-line px-2.5 pt-3 text-xs text-fg-3">On-prem · no data leaves your network</p>
      </nav>
      <div className="flex min-w-0 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5 md:px-6">
          <span className="font-display text-lg font-extrabold tracking-tight md:hidden">assayr</span>
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
