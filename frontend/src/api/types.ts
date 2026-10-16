export interface RoleGrant { role: string; scope_id: string | null }
export interface Me {
  id: string
  email: string
  full_name: string
  is_active: boolean
  department?: string | null
  must_change_password?: boolean
  roles: RoleGrant[]
  permissions: string[]
}
/** Staff whose only role is Employee see My training and nothing else. */
export const isEmployeeOnly = (me: Pick<Me, "roles">) =>
  me.roles.length > 0 && me.roles.every((r) => r.role === "employee")
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

export interface Level { likelihood: number; consequence: number; score: number; band: string; band_label: string }
export interface Band {
  key: string
  label: string
  min: number
  max: number
  above_appetite: boolean
  treatment_required: boolean
  authority: string
  review_days: number
  rule: string
}
export interface Methodology {
  version_no: number
  name: string
  likelihood: { level: number; label: string; guidance: string }[]
  consequence: {
    levels: { level: number; label: string }[]
    dimensions: { key: string; label: string; guidance: string[] }[]
  }
  bands: Band[]
}
export interface LibraryItem { code: string; name: string; category: string; description: string | null; is_custom: boolean }
export interface RiskTemplate {
  code: string
  title: string
  scenario: string
  category: string
  threat_codes: string[]
  vulnerability_codes: string[]
  control_codes: string[]
  likelihood: number
  consequence: Record<string, number>
}
export interface RiskLibrary { threats: LibraryItem[]; vulnerabilities: LibraryItem[]; templates: RiskTemplate[] }
export interface RiskRow {
  id: string
  code: string
  title: string
  category: string | null
  approach: string
  owner: Owner | null
  status: string
  inherent: Level | null
  current: Level | null
  target: Level | null
  treatment_option: string | null
  progress: { done: number; total: number }
  review_due: string | null
  acceptance_expires: string | null
}
export interface Assessment {
  id: string
  likelihood: number | null
  consequence: Record<string, number>
  inherent: Level | null
  suggested: Level | null
  current: Level | null
  current_reason: string | null
  target: Level | null
  rationale: string | null
  finalized_at: string | null
  assessed_by: string | null
  methodology_version: number
}
export interface RiskTask {
  id: string
  title: string
  assignee: Owner | null
  due: string | null
  status: string
  done_at: string | null
}
export interface RiskAcceptance {
  band: string
  score: number
  authority: string
  statement: string
  accepted_by: string | null
  accepted_at: string
  expires_at: string
}
export interface RiskDetail extends RiskRow {
  description: string | null
  template_code: string | null
  threats: { code: string; name: string }[]
  vulnerabilities: { code: string; name: string }[]
  assets: { id: string; code: string; name: string }[]
  controls: { code: string; title: string; status: string; axis: string }[]
  draft: Assessment | null
  latest: Assessment | null
  history: Assessment[]
  treatment: { option: string | null; note: string | null; budget: string | null; due: string | null }
  actions: RiskTask[]
  acceptance: RiskAcceptance | null
  required_authority: string | null
  can_accept: boolean
  can_edit: boolean
  can_assign: boolean
  closed_at: string | null
  close_reason: string | null
}
export interface SnapshotSummary {
  id: string
  label: string
  taken_at: string
  taken_by: string | null
  methodology_version: number
  risk_count: number
}
export interface SnapshotCompare {
  base: SnapshotSummary
  head: SnapshotSummary
  added: string[]
  removed: string[]
  changed: { code: string; title: string; changes: { field: string; before: string | null; after: string | null }[] }[]
}
export interface Asset {
  id: string
  code: string
  name: string
  type: string
  owner: Owner | null
  classification: string
  confidentiality: number
  integrity: number
  availability: number
  criticality: number
  location: string | null
  description: string | null
  lifecycle: string
}
export interface Person { id: string; full_name: string; email: string; roles: string[] }

export interface SoaSource { kind: string; label: string; ref: string | null }
export interface SoaItem {
  code: string
  title: string
  theme: string | null
  applicable: boolean
  sources: SoaSource[]
  justification: string | null
  exclusion_reason: string | null
  implementation_status: string
  status: string
  evidence_verified: number
  evidence_required: number
  owner: string | null
}
export interface SoaChecks {
  orphans: string[]
  excluded_mitigating: { code: string; risks: string[] }[]
  untreated_risks: string[]
  ok: boolean
}
export interface Soa { items: SoaItem[]; checks: SoaChecks }
export interface SoaVersion {
  version_no: number
  status: string
  prepared_by: string | null
  prepared_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  applicable: number
  excluded: number
}
