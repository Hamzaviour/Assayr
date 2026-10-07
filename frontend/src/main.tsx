import "@fontsource/ibm-plex-sans/400.css"
import "@fontsource/ibm-plex-sans/500.css"
import "@fontsource/ibm-plex-sans/600.css"
import "@fontsource/ibm-plex-mono/400.css"
import "@fontsource/ibm-plex-mono/500.css"
import "@fontsource/schibsted-grotesk/600.css"
import "@fontsource/schibsted-grotesk/800.css"
import "./styles/global.css"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { Styleguide } from "./pages/Styleguide"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="p-6"><Styleguide /></main>
  </StrictMode>,
)
