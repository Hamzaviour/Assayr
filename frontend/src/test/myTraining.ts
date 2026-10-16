import type { MyAssignment, MyAssignmentDetail } from "../api/training"

export const myRow = (extra: Partial<MyAssignment> = {}): MyAssignment => ({
  id: "as1", course_title: "Security awareness 2026", course_description: "Invented description", status: "assigned",
  overdue: false, due_at: "2026-11-15", completed_at: null, material_count: 2, materials_done: 0, has_assessment: true,
  attempts_used: 0, attempts_left: 3, best_score: null, ...extra,
})

export const myDetail = (extra: Partial<MyAssignmentDetail> = {}): MyAssignmentDetail => ({
  ...myRow(),
  materials: [
    { id: "m1", sort_order: 1, kind: "drive", title: "Phishing video", drive_file_id: "1AbC", preview_url: "https://drive.google.com/file/d/1AbC/preview", filename: null, mime: null, size: null },
    { id: "m2", sort_order: 2, kind: "file", title: "Intro video", drive_file_id: null, preview_url: null, filename: "intro.mp4", mime: "video/mp4", size: 2048 },
    { id: "m3", sort_order: 3, kind: "file", title: "Handbook", drive_file_id: null, preview_url: null, filename: "h.pdf", mime: "application/pdf", size: 2048 },
  ],
  done: [],
  assessment: {
    pass_mark: 80,
    questions: [
      { id: "q1", kind: "single", text: "Invented single?", options: [{ id: "o1", text: "Right" }, { id: "o2", text: "Wrong" }] },
      { id: "q2", kind: "multiple", text: "Invented multiple?", options: [{ id: "o3", text: "A" }, { id: "o4", text: "B" }, { id: "o5", text: "C" }] },
      { id: "q3", kind: "true_false", text: "Invented statement.", options: [{ id: "o6", text: "True" }, { id: "o7", text: "False" }] },
    ],
  },
  assessment_locked: true,
  attempts: [],
  ...extra,
})
