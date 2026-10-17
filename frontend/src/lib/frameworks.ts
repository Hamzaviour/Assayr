/** Which controls list a dashboard framework row opens. */
export type ControlsFramework = "nia" | "iso42001" | "soc2"

/** Dashboard framework code → the `framework` search of /controls; ISO/IEC 27001 is the default list. */
export function controlsFramework(code: string): ControlsFramework | undefined {
  const c = code.toLowerCase()
  if (c.startsWith("nia")) return "nia"
  if (c.startsWith("iso42001")) return "iso42001"
  if (c.startsWith("soc2")) return "soc2"
  return undefined
}

export const isPdppl = (code: string) => code.toLowerCase().startsWith("pdppl")
