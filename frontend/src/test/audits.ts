import type { Audit } from "../api/audits"

export const audit = (extra: Partial<Audit> = {}): Audit => ({
  id: "a1", framework: "nia-2.1", title: "NIA internal audit 2026", period_start: null, period_end: null,
  auditor: { id: "u1", full_name: "Ali Auditor" }, scope_note: null, conclusion: null, status: "in_progress",
  completed_at: null, completed_by: null, created_at: "2026-10-16T09:00:00Z",
  counts: { total: 355, tested: 120, pass: 110, partial: 6, fail: 3, na: 1 }, can_write: true, can_reopen: false, ...extra,
})
