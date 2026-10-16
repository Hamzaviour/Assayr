import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import { usePeople } from "../api/people"
import {
  ASSIGNMENT_STATUS,
  type AssignmentRow,
  type AssignTarget,
  type CourseDetail,
  type QuestionDraft,
  type QuestionKind,
  useAddDrive,
  useAddFile,
  useAssign,
  useCourse,
  useCourseAssignments,
  useCourseStatus,
  useGrantAttempts,
  useMoveMaterial,
  useRemoveMaterial,
  useSaveAssessment,
  useUpdateCourse,
} from "../api/training"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"
import { CompletionRing, CourseStatus } from "./Training"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const FIELD = "rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] text-fg-2"
export const ASSIGNMENT_TONE: Record<AssignmentRow["status"], string> = {
  assigned: "text-idle",
  in_progress: "text-info",
  passed: "text-ok",
  failed: "text-bad",
}
const TRUE_FALSE = [
  { text: "True", is_correct: true },
  { text: "False", is_correct: false },
]

export function CourseEditorPage() {
  const { id } = useParams({ from: "/app/training/$id" })
  const course = useCourse(id)
  if (course.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (course.isError) return <p role="alert">{course.error.message}</p>
  const c = course.data
  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/training" className="hover:text-fg">Training</Link> <span aria-hidden="true">›</span> {c.title}
      </nav>
      <Header course={c} />
      {c.has_assignments && (
        <p className="rounded-lg bg-warn-soft px-4 py-2.5 text-[13px] text-fg">
          People are taking this course, so its materials and questions are locked. You can still add materials, assign
          more people, or archive it and create a new version.
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Materials course={c} />
        <AssessmentEditor course={c} />
      </div>
      <Assign course={c} />
      <People course={c} />
    </div>
  )
}

function Header({ course: c }: { course: CourseDetail }) {
  const setStatus = useCourseStatus(c.id)
  const update = useUpdateCourse(c.id)
  const [due, setDue] = useState(String(c.due_days))
  const [repeat, setRepeat] = useState(c.recurrence_months ? String(c.recurrence_months) : "")
  return (
    <header className="rise relative grid gap-4 overflow-hidden rounded-2xl border border-line bg-surface p-6">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <CompletionRing passed={c.counts.passed} assigned={c.counts.assigned} size={72} />
          <div>
            <h1 className="font-display text-[26px] font-extrabold tracking-tight">{c.title}</h1>
            <p className="mt-1 text-[13px] tabular-nums text-fg-2">
              {c.counts.assigned} assigned · <span className="text-ok">{c.counts.passed} passed</span> ·{" "}
              <span className={c.counts.overdue ? "font-semibold text-bad" : ""}>{c.counts.overdue} overdue</span>
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CourseStatus status={c.status} />
          {c.status !== "published" && (
            <Button size="sm" disabled={c.materials.length === 0 || setStatus.isPending} onClick={() => setStatus.mutate("publish")}>
              Publish
            </Button>
          )}
          {c.status === "published" && (
            <Button size="sm" variant="secondary" onClick={() => setStatus.mutate("archive")}>Archive</Button>
          )}
        </div>
      </div>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          update.mutate({ due_days: Number(due), recurrence_months: repeat ? Number(repeat) : null })
        }}
      >
        <label className={LABEL}>
          Due within (days)
          <input type="number" min={1} max={365} value={due} onChange={(e) => setDue(e.target.value)} className={`${FIELD} w-24`} />
        </label>
        <label className={LABEL}>
          Repeats
          <select value={repeat} onChange={(e) => setRepeat(e.target.value)} className={FIELD}>
            <option value="">One-off</option>
            <option value="6">Every 6 months</option>
            <option value="12">Every year</option>
            <option value="24">Every 2 years</option>
          </select>
        </label>
        <Button type="submit" size="sm" variant="secondary" disabled={update.isPending}>Save schedule</Button>
      </form>
      {(setStatus.isError || update.isError) && (
        <p role="alert" className="text-[13px] text-bad">{(setStatus.error ?? update.error)?.message}</p>
      )}
    </header>
  )
}

function Materials({ course: c }: { course: CourseDetail }) {
  const addDrive = useAddDrive(c.id)
  const addFile = useAddFile(c.id)
  const move = useMoveMaterial(c.id)
  const remove = useRemoveMaterial(c.id)
  const [title, setTitle] = useState("")
  const [url, setUrl] = useState("")
  const error = addDrive.error ?? addFile.error ?? remove.error

  function onDrive(event: FormEvent) {
    event.preventDefault()
    addDrive.mutate({ title: title.trim(), url: url.trim() }, { onSuccess: () => { setTitle(""); setUrl("") } })
  }

  return (
    <section aria-label="Materials" className={`${CARD} grid content-start gap-3`}>
      <h2 className="text-[15px] font-semibold">Materials</h2>
      {c.materials.length === 0 && <p className="text-[13px] text-fg-3">Add a Google Drive video or upload a file.</p>}
      <ol className="grid gap-1.5">
        {c.materials.map((m, i) => (
          <li key={m.id} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2">
            <span className="grid size-7 shrink-0 place-items-center rounded-md bg-primary-soft text-[12px] font-bold text-primary">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-medium">{m.title}</span>
              <span className="text-[12px] text-fg-3">{m.kind === "drive" ? "Google Drive" : (m.filename ?? "File")}</span>
            </span>
            <button type="button" aria-label={`Move ${m.title} up`} disabled={i === 0} onClick={() => move.mutate({ materialId: m.id, sort_order: i - 1 })} className="rounded px-1.5 text-fg-3 hover:bg-subtle disabled:opacity-30">↑</button>
            <button type="button" aria-label={`Move ${m.title} down`} disabled={i === c.materials.length - 1} onClick={() => move.mutate({ materialId: m.id, sort_order: i + 1 })} className="rounded px-1.5 text-fg-3 hover:bg-subtle disabled:opacity-30">↓</button>
            {!c.has_assignments && (
              <button type="button" aria-label={`Remove ${m.title}`} onClick={() => remove.mutate(m.id)} className="rounded px-1.5 text-fg-3 hover:bg-subtle hover:text-bad">×</button>
            )}
          </li>
        ))}
      </ol>
      <form onSubmit={onDrive} className="grid gap-2 border-t border-line pt-3">
        <label className={LABEL}>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} className={FIELD} />
        </label>
        <label className={LABEL}>
          Google Drive link
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://drive.google.com/file/d/…/view" className={FIELD} />
        </label>
        <div>
          <Button type="submit" size="sm" variant="secondary" disabled={!title.trim() || !url.trim() || addDrive.isPending}>Add link</Button>
        </div>
      </form>
      <label className={`${LABEL} border-t border-line pt-3`}>
        Upload a file
        <input
          type="file"
          accept=".mp4,.webm,.pdf,.pptx,.docx"
          disabled={addFile.isPending}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) addFile.mutate({ title: file.name.replace(/\.[^.]+$/, ""), file })
            e.target.value = ""
          }}
          className="text-[13px] text-fg"
        />
      </label>
      <p className="-mt-1 text-[11.5px] text-fg-3">MP4 or WebM video, PDF, Word or PowerPoint, up to 500 MB. Drive videos need internet on the viewer's computer.</p>
      {addFile.isPending && <p role="status" className="text-[12.5px] text-fg-3">Uploading…</p>}
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
    </section>
  )
}

function toDrafts(c: CourseDetail): QuestionDraft[] {
  return (c.assessment?.questions ?? []).map((q) => ({
    kind: q.kind,
    text: q.text,
    options: q.options.map((o) => ({ text: o.text, is_correct: o.is_correct })),
  }))
}

function AssessmentEditor({ course: c }: { course: CourseDetail }) {
  const save = useSaveAssessment(c.id)
  const [questions, setQuestions] = useState<QuestionDraft[]>(() => toDrafts(c))
  const [passMark, setPassMark] = useState(String(c.assessment?.pass_mark ?? 80))
  const [attempts, setAttempts] = useState(String(c.assessment?.max_attempts ?? 3))
  const [shuffle, setShuffle] = useState(c.assessment?.shuffle ?? true)
  const [saved, setSaved] = useState(false)
  useEffect(() => setSaved(false), [questions, passMark, attempts, shuffle])
  const locked = c.has_assignments

  const update = (qi: number, change: Partial<QuestionDraft>) =>
    setQuestions(questions.map((q, i) => (i === qi ? { ...q, ...change } : q)))
  const setKind = (qi: number, kind: QuestionKind) =>
    update(qi, kind === "true_false" ? { kind, options: TRUE_FALSE.map((o) => ({ ...o, is_correct: false })) } : { kind })
  const toggleCorrect = (qi: number, oi: number) => {
    const q = questions[qi]
    const exclusive = q.kind !== "multiple"
    update(qi, {
      options: q.options.map((o, i) => ({ ...o, is_correct: i === oi ? (exclusive ? true : !o.is_correct) : exclusive ? false : o.is_correct })),
    })
  }

  return (
    <section aria-label="Assessment" className={`${CARD} grid content-start gap-3`}>
      <h2 className="text-[15px] font-semibold">Assessment</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className={LABEL}>
          Pass mark (%)
          <input type="number" min={1} max={100} value={passMark} disabled={locked} onChange={(e) => setPassMark(e.target.value)} className={`${FIELD} w-20`} />
        </label>
        <label className={LABEL}>
          Attempts
          <input type="number" min={1} max={20} value={attempts} disabled={locked} onChange={(e) => setAttempts(e.target.value)} className={`${FIELD} w-20`} />
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-[12.5px] text-fg-2">
          <input type="checkbox" checked={shuffle} disabled={locked} onChange={(e) => setShuffle(e.target.checked)} />
          Shuffle questions
        </label>
      </div>
      <ol className="grid gap-3">
        {questions.map((q, qi) => (
          <li key={qi} className="grid gap-2 rounded-lg border border-line p-3">
            <div className="flex gap-2">
              <label className="sr-only" htmlFor={`q${qi}-kind`}>Question {qi + 1} type</label>
              <select id={`q${qi}-kind`} value={q.kind} disabled={locked} onChange={(e) => setKind(qi, e.target.value as QuestionKind)} className={FIELD}>
                <option value="single">One answer</option>
                <option value="multiple">Several answers</option>
                <option value="true_false">True / false</option>
              </select>
              <label className="sr-only" htmlFor={`q${qi}-text`}>Question {qi + 1}</label>
              <input id={`q${qi}-text`} value={q.text} disabled={locked} onChange={(e) => update(qi, { text: e.target.value })} placeholder={`Question ${qi + 1}`} className={`${FIELD} flex-1`} />
              {!locked && (
                <button type="button" aria-label={`Remove question ${qi + 1}`} onClick={() => setQuestions(questions.filter((_, i) => i !== qi))} className="rounded px-1.5 text-fg-3 hover:text-bad">×</button>
              )}
            </div>
            <ul className="grid gap-1.5 pl-1">
              {q.options.map((o, oi) => (
                <li key={oi} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    aria-label={`Question ${qi + 1} option ${oi + 1} is correct`}
                    checked={o.is_correct}
                    disabled={locked}
                    onChange={() => toggleCorrect(qi, oi)}
                    className="accent-[var(--ok)]"
                  />
                  <input
                    aria-label={`Question ${qi + 1} option ${oi + 1}`}
                    value={o.text}
                    disabled={locked || q.kind === "true_false"}
                    onChange={(e) => update(qi, { options: q.options.map((x, i) => (i === oi ? { ...x, text: e.target.value } : x)) })}
                    className={`${FIELD} flex-1 ${o.is_correct ? "border-ok/50 bg-ok-soft" : ""}`}
                  />
                </li>
              ))}
            </ul>
            {!locked && q.kind !== "true_false" && q.options.length < 8 && (
              <button type="button" onClick={() => update(qi, { options: [...q.options, { text: "", is_correct: false }] })} className="justify-self-start text-[12.5px] font-semibold text-primary">
                Add option
              </button>
            )}
          </li>
        ))}
      </ol>
      {!locked && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setQuestions([...questions, { kind: "single", text: "", options: [{ text: "", is_correct: false }, { text: "", is_correct: false }] }])}
          >
            Add question
          </Button>
          <Button
            size="sm"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { pass_mark: Number(passMark), max_attempts: Number(attempts), shuffle, questions },
                { onSuccess: () => setSaved(true) },
              )
            }
          >
            Save assessment
          </Button>
          {saved && <span role="status" className="text-[12.5px] text-ok">Saved</span>}
        </div>
      )}
      {save.isError && <p role="alert" className="text-[13px] text-bad">{save.error.message}</p>}
    </section>
  )
}

type TargetKind = "all" | "department" | "role" | "people"

function Assign({ course: c }: { course: CourseDetail }) {
  const assign = useAssign(c.id)
  const people = usePeople()
  const [kind, setKind] = useState<TargetKind>("all")
  const [department, setDepartment] = useState("")
  const [role, setRole] = useState("employee")
  const [chosen, setChosen] = useState<string[]>([])
  const [due, setDue] = useState(String(c.due_days))

  function target(): AssignTarget | null {
    if (kind === "all") return { target: "all" }
    if (kind === "department") return department.trim() ? { department: department.trim() } : null
    if (kind === "role") return { role }
    return chosen.length ? { user_ids: chosen } : null
  }

  return (
    <section aria-label="Assign" className={`${CARD} grid gap-3`}>
      <h2 className="text-[15px] font-semibold">Assign</h2>
      <p className="text-[12.5px] text-fg-3">
        Everyone, a department or a role is remembered: people who join later get the course automatically.
        {c.rules.length > 0 && ` Assigned to: ${c.rules.map((r) => r.replace(":", " ")).join(", ")}.`}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className={LABEL}>
          Assign to
          <select value={kind} onChange={(e) => setKind(e.target.value as TargetKind)} className={FIELD}>
            <option value="all">Everyone</option>
            <option value="department">A department</option>
            <option value="role">A role</option>
            <option value="people">Named people</option>
          </select>
        </label>
        {kind === "department" && (
          <label className={LABEL}>
            Department
            <input value={department} onChange={(e) => setDepartment(e.target.value)} className={FIELD} />
          </label>
        )}
        {kind === "role" && (
          <label className={LABEL}>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)} className={FIELD}>
              {["employee", "contributor", "control_owner", "risk_owner", "isms_manager", "executive"].map((r) => (
                <option key={r} value={r}>{r.replace("_", " ")}</option>
              ))}
            </select>
          </label>
        )}
        <label className={LABEL}>
          Due within (days)
          <input type="number" min={1} max={365} value={due} onChange={(e) => setDue(e.target.value)} className={`${FIELD} w-24`} />
        </label>
        <Button size="sm" disabled={!target() || assign.isPending} onClick={() => { const t = target(); if (t) assign.mutate({ ...t, due_days: Number(due) }) }}>
          Assign course
        </Button>
      </div>
      {kind === "people" && (
        <fieldset className="grid max-h-48 gap-1 overflow-y-auto rounded-lg border border-line p-2">
          <legend className="px-1 text-[12px] text-fg-3">People</legend>
          {(people.data ?? []).map((p) => (
            <label key={p.id} className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={chosen.includes(p.id)}
                onChange={(e) => setChosen(e.target.checked ? [...chosen, p.id] : chosen.filter((x) => x !== p.id))}
              />
              {p.full_name}
            </label>
          ))}
        </fieldset>
      )}
      {assign.data && <p role="status" className="text-[13px] font-medium text-ok">Assigned to {assign.data.created} people.</p>}
      {assign.isError && <p role="alert" className="text-[13px] text-bad">{assign.error.message}</p>}
    </section>
  )
}

type PeopleFilter = "all" | "overdue" | "failed"

function People({ course: c }: { course: CourseDetail }) {
  const rows = useCourseAssignments(c.id)
  const grant = useGrantAttempts()
  const [filter, setFilter] = useState<PeopleFilter>("all")
  const [granting, setGranting] = useState<string | null>(null)
  const [reason, setReason] = useState("")
  const shown = (rows.data ?? []).filter((r) => (filter === "overdue" ? r.overdue : filter === "failed" ? r.status === "failed" : true))

  return (
    <section aria-label="People" className={`${CARD} grid gap-3`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold">People</h2>
        <div className="flex gap-1.5">
          {(["all", "overdue", "failed"] as PeopleFilter[]).map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1 text-[12px] font-semibold ${filter === f ? "border-primary bg-primary text-on-primary" : "border-line text-fg-2 hover:bg-subtle"}`}
            >
              {f === "all" ? "All" : f === "overdue" ? "Overdue" : "Failed"}
            </button>
          ))}
        </div>
      </div>
      {rows.isSuccess && rows.data.length === 0 && <p className="text-[13px] text-fg-3">Not assigned to anyone yet.</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-fg-3">
              <th className="py-2 pr-3 font-medium">Name</th>
              <th className="py-2 pr-3 font-medium">Department</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 pr-3 font-medium">Due</th>
              <th className="py-2 pr-3 font-medium">Attempts</th>
              <th className="py-2 pr-3 font-medium">Best score</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id} className="border-t border-line align-top">
                <td className="py-2 pr-3 font-medium">{r.full_name}</td>
                <td className="py-2 pr-3 text-fg-2">{r.department ?? "—"}</td>
                <td className={`py-2 pr-3 font-semibold ${ASSIGNMENT_TONE[r.status]}`}>
                  {ASSIGNMENT_STATUS[r.status]}
                  {r.overdue && <span className="ml-1.5 rounded-full bg-bad-soft px-1.5 py-0.5 text-[11px] text-bad">Overdue</span>}
                </td>
                <td className="py-2 pr-3 text-fg-2">{formatDate(r.due_at)}</td>
                <td className="py-2 pr-3 tabular-nums">{r.attempts_allowed ? `${r.attempts} of ${r.attempts_allowed}` : "—"}</td>
                <td className="py-2 pr-3 tabular-nums">{r.best_score === null ? "—" : `${Math.round(r.best_score)}%`}</td>
                <td className="py-2">
                  {r.status === "failed" && granting !== r.id && (
                    <button type="button" aria-label={`Grant attempt to ${r.full_name}`} onClick={() => { setGranting(r.id); setReason("") }} className="text-[12.5px] font-semibold text-primary">
                      Grant attempt
                    </button>
                  )}
                  {granting === r.id && (
                    <div className="grid gap-1.5">
                      <label className={LABEL}>
                        Reason
                        <input value={reason} onChange={(e) => setReason(e.target.value)} className={FIELD} />
                      </label>
                      <Button size="sm" disabled={!reason.trim() || grant.isPending} onClick={() => grant.mutate({ assignmentId: r.id, extra: 1, reason: reason.trim() }, { onSuccess: () => setGranting(null) })}>
                        Grant
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {grant.isError && <p role="alert" className="text-[13px] text-bad">{grant.error.message}</p>}
    </section>
  )
}
