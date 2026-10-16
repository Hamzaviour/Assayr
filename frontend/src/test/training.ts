import type { AssignmentRow, Course, CourseDetail } from "../api/training"

export const course = (extra: Partial<Course> = {}): Course => ({
  id: "c1", title: "Security awareness 2026", description: "Invented description", status: "published",
  recurrence_months: 12, due_days: 30, created_at: "2026-10-16T09:00:00Z", material_count: 2, question_count: 3,
  counts: { assigned: 40, passed: 30, in_progress: 4, overdue: 5, failed: 1 }, ...extra,
})

export const courseDetail = (extra: Partial<CourseDetail> = {}): CourseDetail => ({
  ...course({ status: "draft", counts: { assigned: 0, passed: 0, in_progress: 0, overdue: 0, failed: 0 } }),
  materials: [
    { id: "m1", sort_order: 1, kind: "drive", title: "Phishing video", drive_file_id: "1AbC", preview_url: "https://drive.google.com/file/d/1AbC/preview", filename: null, mime: null, size: null },
    { id: "m2", sort_order: 2, kind: "file", title: "Handbook", drive_file_id: null, preview_url: null, filename: "h.pdf", mime: "application/pdf", size: 2048 },
  ],
  assessment: null,
  rules: [],
  has_assignments: false,
  ...extra,
})

export const assignmentRow = (extra: Partial<AssignmentRow> = {}): AssignmentRow => ({
  id: "as1", user_id: "u2", full_name: "Omar Ali", email: "omar@acme.com", department: "Finance", status: "failed",
  overdue: false, assigned_at: "2026-10-01T09:00:00Z", due_at: "2026-10-31", completed_at: null, attempts: 3,
  attempts_allowed: 3, best_score: 60, ...extra,
})
