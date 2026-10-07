import "@fontsource/ibm-plex-sans/400.css"
import "@fontsource/ibm-plex-sans/500.css"
import "@fontsource/ibm-plex-sans/600.css"
import "@fontsource/ibm-plex-mono/400.css"
import "@fontsource/ibm-plex-mono/500.css"
import "@fontsource/schibsted-grotesk/600.css"
import "@fontsource/schibsted-grotesk/800.css"
import "./styles/global.css"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { ApiError } from "./api/client"
import { createAppRouter } from "./router"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 },
  },
})
const router = createAppRouter()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
