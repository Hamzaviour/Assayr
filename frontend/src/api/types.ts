export interface RoleGrant { role: string; scope_id: string | null }
export interface Me {
  id: string
  email: string
  full_name: string
  is_active: boolean
  roles: RoleGrant[]
  permissions: string[]
}
export interface Owner { id: string; full_name: string }
export interface ControlSummary {
  id: string
  scope_id: string
  code: string
  title: string
  theme: string | null
  status: string
  implementation_status: string
  owner: Owner | null
  evidence_required: number
  score: number | null
}
export interface ControlPage { items: ControlSummary[]; next_cursor: number | null }
export interface EvidenceSlot {
  id: string
  name: string
  evidence_type: string
  required: boolean
  freshness_days: number | null
  rules: string[]
  state: SlotState
  artefact: SlotArtefact | null
}
export interface ControlDetail extends ControlSummary {
  description: string | null
  review_frequency: string | null
  default_owner_role: string | null
  implementation_text: string | null
  slots: EvidenceSlot[]
  requirements: { ref: string; title: string }[]
  attestation: Attestation | null
}
export interface ControlStats {
  scope_id: string
  total: number
  by_status: Record<string, number>
  by_theme: Record<string, number>
}
export type SlotState = "verified" | "expiring" | "expired_grace" | "expired" | "pending" | "rejected" | "missing"
export interface SlotArtefact {
  link_id: string
  version_id: string
  filename: string
  state: string
  confidence: number | null
  evidence_date: string | null
  expires_on: string | null
}
export interface Attestation { attested_at: string; valid_until: string; by: string | null; statement: string }
export interface RuleResult {
  seq: number
  code: string
  name: string
  status: "pass" | "warn" | "fail" | "skipped"
  reason: string
  fix_hint: string | null
  excerpt: string | null
}
export interface ArtefactLink {
  id: string
  state: string
  confidence: number | null
  evidence_date: string | null
  expires_on: string | null
  slot_id: string
  slot_name: string
  control_code: string
  control_title: string
  artefact_id: string
  version_id: string
  version_no: number
  filename: string
  size: number
  mime: string | null
  uploaded_at: string
  uploaded_by: string | null
  decided_by: string | null
  decision_reason: string | null
  rules_planned: number
  rules: RuleResult[]
  text_preview: string | null
}
export interface ReviewItem {
  link_id: string
  control_code: string
  control_title: string
  slot_name: string
  filename: string
  confidence: number | null
  uploaded_by: string | null
  uploaded_at: string
}
export interface Readiness {
  scope_id: string
  readiness: number | null
  status_counts: Record<string, number>
  by_theme: Record<string, number | null>
  trend: { date: string; readiness: number }[]
}
