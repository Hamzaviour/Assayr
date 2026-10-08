import { api, ApiError } from "./client"
import { json, mockApi } from "../test/render"

test("GET requests do not send the CSRF header", async () => {
  document.cookie = "assayr_csrf=token-123; path=/"
  const calls = mockApi({ "GET /auth/me": () => json(200, { ok: true }) })
  await api("/auth/me")
  expect(new Headers(calls[0].init.headers).has("X-CSRF-Token")).toBe(false)
})

test("POST requests send the CSRF header from the cookie and a JSON content type", async () => {
  document.cookie = "assayr_csrf=token-123; path=/"
  const calls = mockApi({ "POST /auth/logout": () => json(204, null) })
  await expect(api("/auth/logout", { method: "POST", body: "{}" })).resolves.toBeUndefined()
  const headers = new Headers(calls[0].init.headers)
  expect(headers.get("X-CSRF-Token")).toBe("token-123")
  expect(headers.get("Content-Type")).toBe("application/json")
})

test("errors carry the server's message", async () => {
  mockApi({ "GET /controls/A.9.99": () => json(404, { detail: "Control not found." }) })
  await expect(api("/controls/A.9.99")).rejects.toEqual(new ApiError(404, "Control not found."))
})

test("401 responses announce that the session ended", async () => {
  mockApi({ "GET /auth/me": () => json(401, { detail: "Not signed in." }) })
  const listener = vi.fn()
  window.addEventListener("assayr:unauthorized", listener)
  await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError)
  window.removeEventListener("assayr:unauthorized", listener)
  expect(listener).toHaveBeenCalledOnce()
})

test("FormData bodies keep the browser's multipart content type", async () => {
  const calls = mockApi({ "POST /controls/A.5.1/slots/s1/artefacts": () => json(202, { id: "l1" }) })
  const form = new FormData()
  form.set("file", new File(["x"], "a.pdf"))
  await api("/controls/A.5.1/slots/s1/artefacts", { method: "POST", body: form })
  expect(new Headers(calls[0].init.headers).has("Content-Type")).toBe(false)
})
