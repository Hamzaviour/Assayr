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
}
export interface ControlPage { items: ControlSummary[]; next_cursor: number | null }
export interface EvidenceSlot {
  id: string
  name: string
  evidence_type: string
  required: boolean
  freshness_days: number | null
  rules: string[]
}
export interface ControlDetail extends ControlSummary {
  description: string | null
  review_frequency: string | null
  default_owner_role: string | null
  implementation_text: string | null
  slots: EvidenceSlot[]
  requirements: { ref: string; title: string }[]
}
export interface ControlStats {
  scope_id: string
  total: number
  by_status: Record<string, number>
  by_theme: Record<string, number>
}
