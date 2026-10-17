import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { controlsFramework, isPdppl } from "../lib/frameworks"

/** A framework name that opens its controls: ISO 27001, NIA, ISO 42001 or SOC 2; PDPPL opens the privacy obligations. */
export function FrameworkLink({ code, className, children }: { code: string; className: string; children: ReactNode }) {
  if (isPdppl(code)) {
    return <Link to="/privacy" search={{ tab: "pdppl" }} className={className}>{children}</Link>
  }
  const framework = controlsFramework(code)
  return <Link to="/controls" search={framework ? { framework } : {}} className={className}>{children}</Link>
}
