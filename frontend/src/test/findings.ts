import type { CorrectiveAction, Finding, FindingDetail } from "../api/findings"

export const finding = (extra: Partial<Finding> = {}): Finding => ({
  id: "f1", code: "F-001", title: "A.5.1: Fail", grade: "major", status: "action_planned", source: "internal_audit",
  framework: "iso27001", ref: "A.5.1", owner: { id: "u2", full_name: "Omar Owner" }, due_date: "2026-11-01", overdue: false,
  audit: { id: "a1", title: "ISO internal audit 2026" }, audit_item_id: "i1", actions_open: 1, actions_total: 1, risk: null,
  raised_at: "2026-10-17T09:00:00Z", closed_at: null, ...extra,
})

export const action = (extra: Partial<CorrectiveAction> = {}): CorrectiveAction => ({
  id: "c1", seq: 1, description: "Invented corrective action", owner: { id: "u3", full_name: "Dina Doer" },
  due_date: "2026-10-30", status: "open", overdue: false, done_at: null, done_note: null, files: [],
  can_edit: true, can_complete: true, ...extra,
})

export const detail = (extra: Partial<FindingDetail> = {}): FindingDetail => ({
  ...finding(), description: "Invented description", root_cause: "Invented root cause", correction: null,
  response: null, raised_by: { id: "u1", full_name: "Ali Auditor" }, actions: [action()], verifications: [],
  can_edit: true, can_edit_capa: true, can_add_action: true, can_verify: false, can_close: false,
  can_reopen: false, can_raise_risk: true, ...extra,
})
