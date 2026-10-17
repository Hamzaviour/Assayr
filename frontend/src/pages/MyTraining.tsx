import { Link } from "@tanstack/react-router"
import type { CSSProperties } from "react"
import { type MyAssignment, useMyAssignments } from "../api/training"
import { ProgressBar } from "../components/charts"
import { formatDate } from "../lib/format"
import { Status } from "../components/Status"

const order = (i: number) => ({ "--i": i }) as CSSProperties

export const MY_STATUS_TONE: Record<MyAssignment["status"], string> = {
  assigned: "bg-subtle text-fg-2 border-line",
  in_progress: "bg-primary-soft text-primary border-primary/25",
  passed: "bg-ok-soft text-ok border-ok/25",
  failed: "bg-bad-soft text-bad border-bad/25",
}

export function MyStatus({ a }: { a: Pick<MyAssignment, "status" | "overdue"> }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Status area="assignment" value={a.status} />
      {a.overdue && <span className="inline-flex rounded-full bg-bad px-2 py-0.5 text-[11.5px] font-semibold text-white">Overdue</span>}
    </span>
  )
}

export function MyTrainingPage() {
  const mine = useMyAssignments()
  const list = mine.data ?? []
  const todo = list.filter((a) => a.status !== "passed").length

  return (
    <div className="mx-auto grid max-w-4xl gap-5">
      <header className="brand-surface rise relative overflow-hidden rounded-2xl px-6 py-7 text-on-brand-2 md:px-8" style={order(0)}>
        <p className="mb-1 text-[12px] font-semibold uppercase tracking-[0.1em] text-on-brand-3">Security awareness</p>
        <h1 className="font-display text-[28px] font-extrabold tracking-tight text-on-brand">My training</h1>
        <p className="mt-1 text-[14px]">{mine.isSuccess && (todo ? `${todo} to do` : "You're all caught up.")}</p>
      </header>
      {mine.isError && <p role="alert">{mine.error.message}</p>}
      {mine.isPending && <div className="h-32 animate-pulse rounded-2xl bg-subtle" aria-label="Loading" />}
      {mine.isSuccess && list.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line-2 p-8 text-center text-fg-3">You have no training assigned right now.</p>
      )}
      <ul className="grid gap-3">
        {list.map((a, i) => (
          <li key={a.id} className="lift rise relative overflow-hidden rounded-2xl border border-line bg-surface p-5" style={order(i + 1)}>
            <span
              aria-hidden="true"
              className={`absolute inset-y-0 left-0 w-[4px] ${a.status === "passed" ? "bg-ok" : a.overdue ? "bg-bad" : "bg-gradient-to-b from-brand to-brand-deep"}`}
            />
            <div className="flex flex-wrap items-start justify-between gap-3">
              <Link to="/my-training/$id" params={{ id: a.id }} className="text-[16.5px] font-semibold hover:text-primary">
                {a.course_title}
              </Link>
              <MyStatus a={a} />
            </div>
            <p className="mt-1 text-[12.5px] text-fg-3">
              {a.status === "passed" && a.completed_at ? `Completed ${formatDate(a.completed_at)}` : `Due ${formatDate(a.due_at)}`}
              {a.best_score !== null && ` · best score ${Math.round(a.best_score)}%`}
            </p>
            <div className="mt-3 grid gap-1">
              <ProgressBar
                value={a.materials_done}
                max={a.material_count}
                label={`${a.course_title} materials done`}
                color={a.status === "passed" ? "var(--ok)" : "var(--primary)"}
              />
              <p className="text-[12px] text-fg-2">
                {a.materials_done} of {a.material_count} materials{a.has_assessment ? " · assessment at the end" : ""}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
