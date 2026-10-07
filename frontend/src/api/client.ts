export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`
  const found = document.cookie.split("; ").find((c) => c.startsWith(prefix))
  return found ? decodeURIComponent(found.slice(prefix.length)) : undefined
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("assayr_csrf")
    if (csrf) headers.set("X-CSRF-Token", csrf)
  }
  const response = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: "same-origin" })
  if (response.status === 401) window.dispatchEvent(new CustomEvent("assayr:unauthorized"))
  if (!response.ok) {
    let message = response.statusText || `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body?.detail === "string") message = body.detail
    } catch {
      /* non-JSON error body: keep the status text */
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
