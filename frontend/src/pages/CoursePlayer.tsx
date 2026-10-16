import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import {
  type AttemptResult,
  type Material,
  type MyAssignmentDetail,
  myMaterialFileUrl,
  useMaterialDone,
  useMyAssignment,
  useSubmitAttempt,
} from "../api/training"
import { Button } from "../components/Button"
import { ProgressBar } from "../components/charts"
import { formatDate } from "../lib/format"
import { MyStatus } from "./MyTraining"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const isVideo = (m: Material) => m.kind === "drive" || (m.mime ?? "").startsWith("video/")

export function CoursePlayerPage() {
  const { id } = useParams({ from: "/app/my-training/$id" })
  const assignment = useMyAssignment(id)
  if (assignment.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (assignment.isError) return <p role="alert">{assignment.error.message}</p>
  const a = assignment.data
  const done = new Set(a.done)
  return (
    <div className="mx-auto grid max-w-4xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/my-training" className="hover:text-fg">My training</Link> <span aria-hidden="true">›</span> {a.course_title}
      </nav>
      <header className="rise relative grid gap-3 overflow-hidden rounded-2xl border border-line bg-surface p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand via-brand-bright to-brand-deep" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{a.course_title}</h1>
          <MyStatus a={a} />
        </div>
        {a.course_description && <p className="text-[14px] text-fg-2">{a.course_description}</p>}
        <ProgressBar value={a.materials.filter((m) => done.has(m.id)).length} max={a.materials.length} label="Materials done" />
        <p className="text-[12.5px] text-fg-3">Due {formatDate(a.due_at)}</p>
      </header>
      <ol className="grid gap-4">
        {a.materials.map((m, i) => (
          <MaterialStep key={m.id} a={a} m={m} index={i} done={done.has(m.id)} />
        ))}
      </ol>
      <AssessmentStep a={a} />
    </div>
  )
}

function MaterialStep({ a, m, index, done }: { a: MyAssignmentDetail; m: Material; index: number; done: boolean }) {
  const markDone = useMaterialDone(a.id)
  const [ended, setEnded] = useState(false)
  const uploadedVideo = m.kind === "file" && isVideo(m)
  const url = myMaterialFileUrl(a.id, m.id)
  return (
    <li className={`${CARD} rise grid gap-3`}>
      <div className="flex items-center gap-3">
        <span className={`grid size-8 shrink-0 place-items-center rounded-full text-[13px] font-bold ${done ? "bg-ok text-white" : "bg-primary-soft text-primary"}`}>
          {done ? "✓" : index + 1}
        </span>
        <h2 className="flex-1 text-[15.5px] font-semibold">{m.title}</h2>
        {done && <span className="text-[12.5px] font-semibold text-ok">Done</span>}
      </div>
      {m.kind === "drive" && m.preview_url && (
        <div className="aspect-video overflow-hidden rounded-xl bg-black">
          <iframe title={m.title} src={m.preview_url} allow="autoplay; fullscreen" allowFullScreen className="h-full w-full" />
        </div>
      )}
      {uploadedVideo && (
        <video controls preload="metadata" src={url} onEnded={() => setEnded(true)} className="w-full rounded-xl bg-black">
          <track kind="captions" />
        </video>
      )}
      {m.kind === "file" && !uploadedVideo && (
        <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 font-semibold text-primary hover:underline">
          Open {m.title} <span className="text-[12px] font-normal text-fg-3">{m.filename}</span>
        </a>
      )}
      {m.kind === "drive" && <p className="text-[12px] text-fg-3">Plays from Google Drive; needs internet on this computer.</p>}
      {!done && (
        <div>
          <Button
            size="sm"
            disabled={(uploadedVideo && !ended) || markDone.isPending}
            onClick={() => markDone.mutate(m.id)}
          >
            {isVideo(m) ? `I have watched ${m.title}` : `I have read ${m.title}`}
          </Button>
          {uploadedVideo && !ended && <p className="mt-1 text-[12px] text-fg-3">Watch to the end to confirm.</p>}
        </div>
      )}
      {markDone.isError && <p role="alert" className="text-[13px] text-bad">{markDone.error.message}</p>}
    </li>
  )
}

function AssessmentStep({ a }: { a: MyAssignmentDetail }) {
  const submit = useSubmitAttempt(a.id)
  const [answers, setAnswers] = useState<Record<string, string[]>>({})
  const [result, setResult] = useState<AttemptResult | null>(null)
  if (!a.assessment) {
    return a.status === "passed" ? <p className={`${CARD} font-semibold text-ok`}>Course complete. Well done.</p> : null
  }
  const questions = a.assessment.questions
  const answered = questions.filter((q) => (answers[q.id] ?? []).length > 0).length

  if (a.status === "passed" && !result) {
    return (
      <section className={`${CARD} border-ok/40 bg-ok-soft`}>
        <h2 className="text-[16px] font-semibold text-ok">You passed this course</h2>
        {a.best_score !== null && <p className="text-[13.5px] text-fg-2">Best score {Math.round(a.best_score)}%.</p>}
      </section>
    )
  }
  if (a.assessment_locked) {
    return (
      <section className={`${CARD} border-dashed`}>
        <h2 className="text-[15.5px] font-semibold">Assessment</h2>
        <p className="text-[13.5px] text-fg-2">Finish all {a.materials.length} materials to unlock the assessment.</p>
      </section>
    )
  }
  if (!result && a.attempts_left === 0) {
    return (
      <section className={`${CARD} border-bad/40 bg-bad-soft`}>
        <h2 className="text-[15.5px] font-semibold text-bad">Assessment</h2>
        <p className="text-[13.5px]">You have used all your attempts. Ask your ISMS manager for another attempt.</p>
      </section>
    )
  }

  const toggle = (qid: string, oid: string, multiple: boolean) => {
    const current = answers[qid] ?? []
    setAnswers({ ...answers, [qid]: multiple ? (current.includes(oid) ? current.filter((x) => x !== oid) : [...current, oid]) : [oid] })
  }
  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit.mutate(answers, { onSuccess: setResult })
  }
  const wrong = new Set(result?.wrong ?? [])

  return (
    <>
      {result && (
        <section aria-label="Your result" className={`${CARD} rise grid gap-2 ${result.passed ? "border-ok/40 bg-ok-soft" : "border-warn/40 bg-warn-soft"}`}>
          <p className={`font-display text-[40px] font-extrabold leading-none ${result.passed ? "text-ok" : "text-warn"}`}>{Math.round(result.score)}%</p>
          <p className="text-[15px] font-semibold">{result.passed ? "Passed. Well done." : "Not passed yet"}</p>
          {!result.passed && (
            <p className="text-[13px] text-fg-2">
              {result.wrong.length} {result.wrong.length === 1 ? "question" : "questions"} to review. You need {a.assessment.pass_mark}% to pass.
            </p>
          )}
          {!result.passed && result.attempts_left > 0 && (
            <div>
              <Button size="sm" onClick={() => { setResult(null); setAnswers({}) }}>
                Try again ({result.attempts_left} {result.attempts_left === 1 ? "attempt" : "attempts"} left)
              </Button>
            </div>
          )}
          {!result.passed && result.attempts_left === 0 && (
            <p className="text-[13px] text-bad">You have used all your attempts. Ask your ISMS manager for another attempt.</p>
          )}
        </section>
      )}
      <form aria-label="Assessment" onSubmit={onSubmit} className={`${CARD} grid gap-4`}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[16px] font-semibold">Assessment</h2>
          <span className="text-[12.5px] tabular-nums text-fg-3">{answered} of {questions.length} answered</span>
        </div>
        <ol className="grid gap-4">
          {questions.map((q, qi) => {
            const multiple = q.kind === "multiple"
            return (
              <li key={q.id} className={`grid gap-2 rounded-xl border p-4 ${wrong.has(q.id) ? "border-bad/50 bg-bad-soft" : "border-line"}`}>
                <fieldset className="grid gap-2" disabled={!!result}>
                  <legend className="mb-1 text-[14px] font-semibold">
                    {qi + 1}. {q.text}
                    {multiple && <span className="ml-1 text-[12px] font-normal text-fg-3">(choose all that apply)</span>}
                  </legend>
                  {q.options.map((o) => (
                    <label key={o.id} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13.5px] hover:bg-subtle">
                      <input
                        type={multiple ? "checkbox" : "radio"}
                        name={q.id}
                        checked={(answers[q.id] ?? []).includes(o.id)}
                        onChange={() => toggle(q.id, o.id, multiple)}
                        className="accent-[var(--primary)]"
                      />
                      {o.text}
                    </label>
                  ))}
                </fieldset>
              </li>
            )
          })}
        </ol>
        {!result && (
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={answered < questions.length || submit.isPending}>Submit answers</Button>
            {a.attempts_left !== null && <span className="text-[12.5px] text-fg-3">{a.attempts_left} attempts left</span>}
          </div>
        )}
        {submit.isError && <p role="alert" className="text-[13px] text-bad">{submit.error.message}</p>}
      </form>
    </>
  )
}
