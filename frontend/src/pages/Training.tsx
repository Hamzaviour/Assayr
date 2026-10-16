import { Link, useNavigate } from "@tanstack/react-router"
import { type CSSProperties, type FormEvent, useState } from "react"
import { type Course, trainingReportUrl, useCourses, useCreateCourse, useTrainingSummary } from "../api/training"
import { Button } from "../components/Button"
import { ProgressBar } from "../components/charts"

const order = (i: number) => ({ "--i": i }) as CSSProperties
const R = 26
const C = 2 * Math.PI * R

/** A completion ring: the share of assigned people who passed. */
export function CompletionRing({ passed, assigned, size = 64 }: { passed: number; assigned: number; size?: number }) {
  const pct = assigned ? Math.round((100 * passed) / assigned) : 0
  return (
    <svg role="img" aria-label={`${pct}% passed`} width={size} height={size} viewBox="0 0 64 64" className="shrink-0">
      <circle cx="32" cy="32" r={R} fill="none" stroke="var(--subtle)" strokeWidth="7" />
      <circle
        cx="32"
        cy="32"
        r={R}
        fill="none"
        stroke={pct >= 80 ? "var(--ok)" : pct >= 50 ? "var(--warn)" : "var(--primary)"}
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * C} ${C}`}
        transform="rotate(-90 32 32)"
        className="draw"
      />
      <text x="32" y="36" textAnchor="middle" className="fill-[var(--fg)] text-[14px] font-bold">{pct}%</text>
    </svg>
  )
}

export const COURSE_STATUS: Record<Course["status"], [string, string]> = {
  draft: ["Draft", "bg-transparent text-fg-2 border-line-2 border-dashed"],
  published: ["Published", "bg-ok-soft text-ok border-ok/25"],
  archived: ["Archived", "bg-subtle text-fg-3 border-line"],
}

export function CourseStatus({ status }: { status: Course["status"] }) {
  const [label, tone] = COURSE_STATUS[status]
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${tone}`}>{label}</span>
}

function NewCourse({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateCourse()
  const [title, setTitle] = useState("")
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ title: title.trim() }, { onSuccess: (c) => navigate({ to: "/training/$id", params: { id: c.id } }) })
  }
  return (
    <form onSubmit={onSubmit} className="rise flex flex-wrap items-end gap-2 rounded-2xl border border-line bg-surface p-5">
      <label className="grid flex-1 gap-1 text-[12.5px] text-fg-2">
        Course title
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Security awareness 2026"
          required
          maxLength={200}
          className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
        />
      </label>
      <Button type="submit" size="sm" disabled={!title.trim() || create.isPending}>Create course</Button>
      <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
      {create.isError && <p role="alert" className="w-full text-[13px] text-bad">{create.error.message}</p>}
    </form>
  )
}

export function TrainingPage() {
  const courses = useCourses()
  const summary = useTrainingSummary()
  const [creating, setCreating] = useState(false)
  const list = courses.data ?? []

  return (
    <div className="mx-auto grid max-w-6xl gap-5">
      <header className="rise flex flex-wrap items-end justify-between gap-3" style={order(0)}>
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Assure · ISO 27001 A.6.3</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Training and awareness</h1>
          <p className="mt-1 text-[13px] text-fg-2">Courses with videos, documents and an assessment, assigned to your staff.</p>
        </div>
        <div className="flex gap-2">
          <a
            href={trainingReportUrl}
            className="inline-flex items-center rounded-lg border border-line px-3 py-2 text-[13px] font-semibold text-primary hover:bg-subtle"
          >
            Completion report (Excel)
          </a>
          {!creating && <Button onClick={() => setCreating(true)}>New course</Button>}
        </div>
      </header>
      {creating && <NewCourse onClose={() => setCreating(false)} />}
      {courses.isError && <p role="alert">{courses.error.message}</p>}
      {courses.isSuccess && list.length === 0 && (
        <p className="rounded-xl border border-dashed border-line-2 p-8 text-center text-fg-3">
          No courses yet. Create one, add a Google Drive video or upload a file, then assign it.
        </p>
      )}
      <ul className="grid gap-3 md:grid-cols-2">
        {list.map((c, i) => (
          <li key={c.id} className="lift rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5" style={order(i + 1)}>
            <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
            <div className="flex items-start gap-4">
              <CompletionRing passed={c.counts.passed} assigned={c.counts.assigned} />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <Link to="/training/$id" params={{ id: c.id }} className="text-[16px] font-semibold hover:text-primary">
                    {c.title}
                  </Link>
                  <CourseStatus status={c.status} />
                </div>
                <p className="mt-1 text-[12.5px] text-fg-3">
                  {c.material_count} materials · {c.question_count ? `${c.question_count} questions` : "no assessment"} ·{" "}
                  {c.recurrence_months ? `every ${c.recurrence_months} months` : "one-off"}
                </p>
                <p className="mt-2 flex flex-wrap gap-x-3 text-[12.5px] tabular-nums">
                  <span className="text-fg-2">{c.counts.assigned} assigned</span>
                  <span className="text-ok">{c.counts.passed} passed</span>
                  <span className={c.counts.overdue ? "font-semibold text-bad" : "text-fg-3"}>{c.counts.overdue} overdue</span>
                  {c.counts.failed > 0 && <span className="text-warn">{c.counts.failed} failed</span>}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {summary.data && summary.data.departments.length > 0 && (
        <section className="rise rounded-2xl border border-line bg-surface p-5" aria-labelledby="dept-title" style={order(list.length + 1)}>
          <h2 id="dept-title" className="mb-3 text-[15px] font-semibold">Completion by department</h2>
          <ul className="grid gap-2">
            {summary.data.departments.map((d) => (
              <li key={d.department} className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)_80px] items-center gap-4">
                <span className="text-[13.5px] font-medium">{d.department}</span>
                <ProgressBar
                  value={d.passed}
                  max={d.assigned}
                  label={`${d.department} training completion`}
                  color={(d.completion ?? 0) >= 80 ? "var(--ok)" : (d.completion ?? 0) >= 50 ? "var(--warn)" : "var(--bad)"}
                />
                <span className="text-right text-[13px] tabular-nums text-fg-2">{d.completion ?? 0}%</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
