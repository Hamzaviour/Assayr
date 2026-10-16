import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export type QuestionKind = "single" | "multiple" | "true_false"
export type CourseCounts = { assigned: number; passed: number; in_progress: number; overdue: number; failed: number }

export type Course = {
  id: string
  title: string
  description: string | null
  status: "draft" | "published" | "archived"
  recurrence_months: number | null
  due_days: number
  created_at: string
  material_count: number
  question_count: number
  counts: CourseCounts
}

export type Material = {
  id: string
  sort_order: number
  kind: "drive" | "file"
  title: string
  drive_file_id: string | null
  preview_url: string | null
  filename: string | null
  mime: string | null
  size: number | null
}

export type OptionDraft = { text: string; is_correct: boolean }
export type QuestionDraft = { kind: QuestionKind; text: string; options: OptionDraft[] }
export type Assessment = {
  pass_mark: number
  max_attempts: number
  shuffle: boolean
  questions: (QuestionDraft & { id: string; options: (OptionDraft & { id: string })[] })[]
}

export type CourseDetail = Course & { materials: Material[]; assessment: Assessment | null; rules: string[]; has_assignments: boolean }

export type AssignmentRow = {
  id: string
  user_id: string
  full_name: string
  email: string
  department: string | null
  status: "assigned" | "in_progress" | "passed" | "failed"
  overdue: boolean
  assigned_at: string
  due_at: string
  completed_at: string | null
  attempts: number
  attempts_allowed: number | null
  best_score: number | null
}

export type AssignTarget = { target: "all" } | { department: string } | { role: string } | { user_ids: string[] }

export type TrainingSummary = {
  courses: (CourseCounts & { id: string; title: string; status: string; pass_rate: number | null })[]
  departments: { department: string; assigned: number; passed: number; completion: number | null }[]
}

export const ASSIGNMENT_STATUS: Record<AssignmentRow["status"], string> = {
  assigned: "Not started",
  in_progress: "In progress",
  passed: "Passed",
  failed: "Failed",
}
export const trainingReportUrl = "/api/v1/training/report.xlsx"
export const materialFileUrl = (courseId: string, materialId: string) => `/api/v1/courses/${courseId}/materials/${materialId}/file`

export function useCourses() {
  return useQuery({ queryKey: ["courses"], queryFn: () => api<Course[]>("/courses") })
}

export function useCourse(id: string) {
  return useQuery({ queryKey: ["course", id], queryFn: () => api<CourseDetail>(`/courses/${id}`) })
}

export function useCourseAssignments(id: string) {
  return useQuery({ queryKey: ["course", id, "assignments"], queryFn: () => api<AssignmentRow[]>(`/courses/${id}/assignments`) })
}

export function useTrainingSummary() {
  return useQuery({ queryKey: ["training", "summary"], queryFn: () => api<TrainingSummary>("/training/summary") })
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["courses"] })
    queryClient.invalidateQueries({ queryKey: ["course"] })
    queryClient.invalidateQueries({ queryKey: ["training"] })
    queryClient.invalidateQueries({ queryKey: ["dashboard"] })
  }
}

function useCourseMutation<T, R = unknown>(fn: (body: T) => Promise<R>) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: fn, onSuccess: refresh })
}

export function useCreateCourse() {
  return useCourseMutation((body: { title: string; description?: string }) =>
    api<Course>("/courses", { method: "POST", body: JSON.stringify(body) }),
  )
}

export function useUpdateCourse(id: string) {
  return useCourseMutation((changes: Partial<Pick<Course, "title" | "description" | "recurrence_months" | "due_days">>) =>
    api<CourseDetail>(`/courses/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  )
}

export function useAddDrive(id: string) {
  return useCourseMutation((body: { title: string; url: string }) =>
    api<Material>(`/courses/${id}/materials/drive`, { method: "POST", body: JSON.stringify(body) }),
  )
}

export function useAddFile(id: string) {
  return useCourseMutation(({ title, file }: { title: string; file: File }) => {
    const form = new FormData()
    form.append("title", title)
    form.append("file", file)
    return api<Material>(`/courses/${id}/materials/file`, { method: "POST", body: form })
  })
}

export function useMoveMaterial(id: string) {
  return useCourseMutation(({ materialId, sort_order }: { materialId: string; sort_order: number }) =>
    api<CourseDetail>(`/courses/${id}/materials/${materialId}`, { method: "PATCH", body: JSON.stringify({ sort_order }) }),
  )
}

export function useRemoveMaterial(id: string) {
  return useCourseMutation((materialId: string) => api<CourseDetail>(`/courses/${id}/materials/${materialId}`, { method: "DELETE" }))
}

export function useSaveAssessment(id: string) {
  return useCourseMutation((body: { pass_mark: number; max_attempts: number; shuffle: boolean; questions: QuestionDraft[] }) =>
    api<Assessment | null>(`/courses/${id}/assessment`, { method: "PUT", body: JSON.stringify(body) }),
  )
}

export function useCourseStatus(id: string) {
  return useCourseMutation((action: "publish" | "archive") => api<CourseDetail>(`/courses/${id}/${action}`, { method: "POST" }))
}

export function useAssign(id: string) {
  return useCourseMutation((body: AssignTarget & { due_days?: number }) =>
    api<{ created: number }>(`/courses/${id}/assign`, { method: "POST", body: JSON.stringify(body) }),
  )
}

export function useGrantAttempts() {
  return useCourseMutation(({ assignmentId, extra, reason }: { assignmentId: string; extra: number; reason: string }) =>
    api<AssignmentRow>(`/assignments/${assignmentId}/attempts`, { method: "POST", body: JSON.stringify({ extra, reason }) }),
  )
}
