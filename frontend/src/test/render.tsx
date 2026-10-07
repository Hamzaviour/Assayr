import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router"
import { render } from "@testing-library/react"
import type { Me } from "../api/types"
import { createAppRouter } from "../router"

export const ME: Me = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "sana@acme.com",
  full_name: "Sana Malik",
  is_active: true,
  roles: [{ role: "isms_manager", scope_id: null }],
  permissions: ["audit_log:read", "controls:read", "controls:write"],
}

export const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

type Handler = (url: URL, init: RequestInit) => Response | Promise<Response>

/** Stub fetch. Keys look like "GET /controls" (path after /api/v1, no query string). */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { method: string; url: URL; init: RequestInit }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost")
    const method = (init.method ?? "GET").toUpperCase()
    calls.push({ method, url, init })
    const handler = routes[`${method} ${url.pathname.replace(/^\/api\/v1/, "")}`]
    return handler ? handler(url, init) : json(404, { detail: `No mock for ${method} ${url.pathname}` })
  })
  vi.stubGlobal("fetch", fetchMock)
  return calls
}

export function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}
