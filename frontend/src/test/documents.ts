import type { DocumentRow } from "../api/documents"

export const doc = (id: string, doc_type: DocumentRow["doc_type"], code: string, title: string, extra: Partial<DocumentRow> = {}): DocumentRow => ({
  id, doc_type, code, title, description: null, owner: { id: "u1", full_name: "Sana Malik" }, status: "draft",
  version_label: "1.0", approved_by: null, approved_at: null, review_due: null, review_overdue: false,
  filename: null, size: null, can_edit: true, can_approve: true, ...extra,
})
