/** Personal-data vocabulary shared by Assets and Data privacy (same codes as the API). */
export const PII_CATEGORIES: Record<string, string> = {
  contact: "Contact details",
  national_id: "National ID / QID / passport",
  financial: "Financial",
  health: "Health",
  biometric: "Biometric",
  hr: "Employee / HR records",
  children: "Children's data",
  location: "Location",
  online: "Online identifiers",
  religion: "Religious beliefs",
  criminal: "Criminal records",
  ethnic: "Ethnic origin",
  other: "Other",
}
export const SENSITIVE = new Set(["health", "biometric", "children", "religion", "criminal", "ethnic"])
export const PII_VOLUME: Record<string, string> = {
  lt100: "Fewer than 100",
  "100_1k": "100 – 1,000",
  "1k_10k": "1,000 – 10,000",
  gt10k: "More than 10,000",
}
