import { useQueryClient } from "@tanstack/react-query"
import { Outlet, useLocation, useNavigate } from "@tanstack/react-router"
import { useEffect, useRef } from "react"
import { ApiError } from "../api/client"
import { useMe } from "../auth/session"
import { AppShell } from "../components/AppShell"

export function AppLayout() {
  const me = useMe()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const redirected = useRef(false)
  const signedOut = me.isError && me.error instanceof ApiError && me.error.status === 401

  useEffect(() => {
    // Another request found the session gone: re-check it. Ignore the 401 that /auth/me itself
    // reports, or every failed re-check would trigger the next one.
    const onUnauthorized = () => {
      if (queryClient.isFetching({ queryKey: ["me"] }) === 0) queryClient.invalidateQueries({ queryKey: ["me"] })
    }
    window.addEventListener("assayr:unauthorized", onUnauthorized)
    return () => window.removeEventListener("assayr:unauthorized", onUnauthorized)
  }, [queryClient])

  useEffect(() => {
    // Redirect exactly once: while the navigation is in flight this layout re-renders with the
    // new /login location, and re-reading it would nest ?next= endlessly.
    if (signedOut && !redirected.current) {
      redirected.current = true
      navigate({ to: "/login", search: { next: location.href }, replace: true })
    }
  }, [signedOut, navigate, location.href])

  if (me.isPending || signedOut) return <p role="status" className="p-8 text-fg-3">Loading…</p>
  if (me.isError) {
    return (
      <p role="alert" className="p-8">
        Can't reach the Assayr server. Check that the API is running, then reload this page.
      </p>
    )
  }
  return (
    <AppShell me={me.data}>
      <Outlet />
    </AppShell>
  )
}
