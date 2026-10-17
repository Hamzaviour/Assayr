import type { Activity } from "../api/privacy"

export const activity = (extra: Partial<Activity> = {}): Activity => ({
  id: "p1", code: "PA-001", name: "Payroll", purpose: "Pay salaries", data_subjects: ["employees"],
  data_categories: ["hr", "health"], lawful_basis: "contract", recipients: "Bank", cross_border: true,
  transfer_countries: "UAE", retention: "7 years", security_measures: null, owner: null, status: "active",
  review_due: "2026-01-01", sensitive: true, review_overdue: true,
  assets: [{ id: "a1", code: "AST-001", name: "HR system", criticality_label: "Very high" }], can_edit: true, ...extra,
})
