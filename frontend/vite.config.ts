import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // ASSAYR_API points the dev server at another API, e.g. when an installed Assayr already uses port 8000.
  server: { proxy: { "/api": process.env.ASSAYR_API ?? "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
})
