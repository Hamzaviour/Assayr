import type { Band, Level, Methodology, RiskDetail, RiskRow } from "../api/types"

const BANDS: Band[] = [
  { key: "very_low", label: "Very low", min: 1, max: 3, above_appetite: false, treatment_required: false,
    authority: "risk_owner", review_days: 365, rule: "Accept; the risk owner is aware." },
  { key: "low", label: "Low", min: 4, max: 6, above_appetite: false, treatment_required: false,
    authority: "risk_owner", review_days: 365, rule: "Accept by the risk owner." },
  { key: "medium", label: "Medium", min: 7, max: 10, above_appetite: true, treatment_required: false,
    authority: "risk_owner", review_days: 182, rule: "Treat, or accept with the risk owner's justification." },
  { key: "high", label: "High", min: 11, max: 16, above_appetite: true, treatment_required: true,
    authority: "isms_manager", review_days: 90,
    rule: "A treatment plan is required; the residual risk is accepted by an ISMS manager." },
  { key: "critical", label: "Critical", min: 17, max: 25, above_appetite: true, treatment_required: true,
    authority: "executive", review_days: 31, rule: "Treat immediately; only top management can accept the residual risk." },
]
const DIMENSIONS: [string, string][] = [
  ["financial", "Financial"], ["operational", "Operational"], ["legal", "Legal / regulatory"],
  ["reputation", "Reputation"], ["data", "Data (C/I/A)"],
]

export const METHODOLOGY: Methodology = {
  version_no: 1,
  name: "Assayr default (ISO/IEC 27005:2022)",
  likelihood: ["Rare", "Unlikely", "Possible", "Likely", "Almost certain"].map((label, i) => ({
    level: i + 1, label, guidance: `Likelihood guidance ${i + 1}`,
  })),
  consequence: {
    levels: ["Negligible", "Minor", "Moderate", "Major", "Severe"].map((label, i) => ({ level: i + 1, label })),
    dimensions: DIMENSIONS.map(([key, label]) => ({
      key, label, guidance: [1, 2, 3, 4, 5].map((n) => `${label} guidance ${n}`),
    })),
  },
  bands: BANDS,
}

export function level(likelihood: number, consequence: number): Level {
  const score = likelihood * consequence
  const band = BANDS.find((b) => score >= b.min && score <= b.max)!
  return { likelihood, consequence, score, band: band.key, band_label: band.label }
}

export function riskRow(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    id: "r1", code: "R-001", title: "Ransomware encrypts file servers", category: "Cyber attack",
    approach: "event", owner: { id: "u1", full_name: "Sana Malik" }, status: "assessed",
    inherent: level(4, 5), current: level(4, 4), target: level(2, 4), treatment_option: null,
    progress: { done: 0, total: 0 }, review_due: "2027-01-06", acceptance_expires: null,
    ...overrides,
  }
}

export function riskDetail(overrides: Partial<RiskDetail> = {}): RiskDetail {
  return {
    ...riskRow(),
    description: "Ransomware enters through an unpatched system and encrypts file servers.",
    template_code: "RT01",
    threats: [{ code: "T01", name: "Ransomware" }],
    vulnerabilities: [{ code: "V17", name: "No backups, or backups never tested" }],
    assets: [],
    controls: [{ code: "A.8.13", title: "Information backup", status: "compliant", axis: "likelihood" }],
    draft: null, latest: null, history: [],
    treatment: { option: null, note: null, budget: null, due: null },
    actions: [], acceptance: null, required_authority: "isms_manager", can_accept: true, can_edit: true, can_assign: true,
    closed_at: null, close_reason: null,
    ...overrides,
  }
}
