import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { usePeople } from "../api/people"
import {
  AUTHORITY_LABEL, TASK_STATUS_LABEL, TREATMENT_LABEL, useAcceptRisk, useAddAction, useCloseRisk, useRisk,
  useSetTreatment, useUpdateRisk, useUpdateTask,
} from "../api/risks"
import type { Level, RiskDetail } from "../api/types"
import { Button } from "../components/Button"
import { LevelPill, RiskStatusPill } from "../components/LevelPill"
import { OwnerPicker } from "../components/OwnerPicker"
import { StatusPill } from "../components/StatusPill"
import { formatDate } from "../lib/format"

const card = "rounded-xl border border-line bg-surface p-5"
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const OPTION_HELP: Record<string, string> = {
  modify: "Add or improve controls",
  retain: "Accept the risk as it is",
  avoid: "Stop the activity that causes it",
  share: "Insurance or outsourcing",
}

export function RiskDetailPage() {
  const { code } = useParams({ from: "/app/risks/$code" })
  const risk = useRisk(code)
  if (risk.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (risk.isError) return <p role="alert">{risk.error.message}</p>
  const r = risk.data
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span>{" "}
        <span className="font-mono">{r.code}</span>
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">{r.code}{r.category ? ` · ${r.category}` : ""}</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{r.title}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-[13px] text-fg-2">
            {r.can_assign ? <OwnerField risk={r} /> : <span>Owner: {r.owner?.full_name ?? "Unassigned"}</span>}
            {r.review_due && <span>· Next review {formatDate(r.review_due)}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {r.can_edit && !r.closed_at && (
            <Link to="/risks/$code/assess" params={{ code: r.code }}
              className="rounded-lg bg-primary px-3 py-1.5 text-[13px] font-medium text-on-primary hover:bg-primary-hover">
              {r.draft ? "Continue assessment" : r.latest ? "Reassess" : "Assess"}
            </Link>
          )}
          <RiskStatusPill status={r.status} />
        </div>
      </header>
      <Levels risk={r} />
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid content-start gap-4">
          <Scenario risk={r} />
          <MitigatingControls risk={r} />
          <Treatment risk={r} />
          <History risk={r} />
        </div>
        <div className="grid content-start gap-4">
          <Acceptance risk={r} />
          {r.closed_at && (
            <section className={card}>
              <h2 className="text-[15px] font-semibold">Closed</h2>
              <p className="text-[13px] text-fg-2">{formatDate(r.closed_at)} · {r.close_reason}</p>
            </section>
          )}
          {r.can_edit && <CloseRisk risk={r} />}
        </div>
      </div>
    </div>
  )
}

function Levels({ risk }: { risk: RiskDetail }) {
  const items: [string, Level | null][] = [["Inherent", risk.inherent], ["Current", risk.current], ["Target", risk.target]]
  return (
    <section aria-label="Risk levels" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-5 py-4">
      {items.map(([label, value], index) => (
        <div key={label} className="flex items-center gap-2">
          {index > 0 && <span aria-hidden="true" className="text-fg-3">→</span>}
          <span className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{label}</span>
          <LevelPill level={value} />
        </div>
      ))}
    </section>
  )
}

function Scenario({ risk }: { risk: RiskDetail }) {
  const groups: [string, { code: string; name: string }[]][] = [
    ["Threats", risk.threats],
    ["Vulnerabilities", risk.vulnerabilities],
    ["Assets", risk.assets.map((a) => ({ code: a.code, name: a.name }))],
  ]
  return (
    <section className={`${card} grid gap-3`}>
      <h2 className="text-[15px] font-semibold">Scenario</h2>
      <p className="text-[13.5px] text-fg-2">{risk.description || "No scenario written yet."}</p>
      {groups.map(([label, items]) => (
        <div key={label} className="grid gap-1.5">
          <p className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{label}</p>
          {items.length ? (
            <ul className="flex flex-wrap gap-1.5">
              {items.map((i) => (
                <li key={i.code} className="rounded-md bg-subtle px-2 py-0.5 text-[12.5px]">
                  <span className="font-mono text-fg-3">{i.code}</span> {i.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-fg-3">None</p>
          )}
        </div>
      ))}
    </section>
  )
}

function MitigatingControls({ risk }: { risk: RiskDetail }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-[15px] font-semibold">Mitigating controls</h2>
      {risk.controls.length === 0 ? (
        <p className="text-[13px] text-fg-3">No controls linked yet.</p>
      ) : (
        <ul className="grid gap-2">
          {risk.controls.map((c) => (
            <li key={c.code} className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0">
                <span className="font-mono text-[12.5px] text-fg-3">{c.code}</span>{" "}
                <Link to="/controls/$code" params={{ code: c.code }} className="hover:text-primary">{c.title}</Link>
                <span className="text-[12px] text-fg-3"> · reduces {c.axis}</span>
              </span>
              <StatusPill status={c.status} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Treatment({ risk }: { risk: RiskDetail }) {
  const setTreatment = useSetTreatment(risk.code)
  const [option, setOption] = useState(risk.treatment.option ?? "")
  const [note, setNote] = useState(risk.treatment.note ?? "")
  const [budget, setBudget] = useState(risk.treatment.budget ?? "")
  const [due, setDue] = useState(risk.treatment.due ?? "")
  const editable = risk.can_edit && !["draft", "closed"].includes(risk.status)

  function save(event: FormEvent) {
    event.preventDefault()
    setTreatment.mutate({ option, note: note.trim() || null, budget: budget.trim() || null, due: due || null })
  }

  return (
    <section className={`${card} grid gap-3`} aria-labelledby="treatment-heading">
      <h2 id="treatment-heading" className="text-[15px] font-semibold">Treatment</h2>
      {editable ? (
        <form onSubmit={save} className="grid gap-3">
          <fieldset className="grid gap-2 sm:grid-cols-2">
            <legend className="sr-only">Treatment option</legend>
            {Object.keys(TREATMENT_LABEL).map((key) => (
              <label key={key} className="flex items-start gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
                <input type="radio" name="treatment" value={key} checked={option === key} onChange={() => setOption(key)}
                  aria-label={TREATMENT_LABEL[key]} aria-describedby={`treatment-${key}-help`} />
                <span>
                  <span className="font-medium">{TREATMENT_LABEL[key]}</span>
                  <span id={`treatment-${key}-help`} className="block text-fg-3">{OPTION_HELP[key]}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <label htmlFor="treatment-note" className="text-[13px] font-medium">
            {option === "avoid" ? "Decision" : option === "share" ? "Contract or insurance reference" : "Notes"}
          </label>
          <textarea id="treatment-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={input} />
          <div className="flex flex-wrap gap-3">
            <div className="grid gap-1">
              <label htmlFor="treatment-budget" className="text-[13px] font-medium">Budget</label>
              <input id="treatment-budget" value={budget} onChange={(e) => setBudget(e.target.value)} className={input} />
            </div>
            <div className="grid gap-1">
              <label htmlFor="treatment-due" className="text-[13px] font-medium">Due date</label>
              <input id="treatment-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} />
            </div>
          </div>
          {setTreatment.isError && <p role="alert" className="text-[13px] text-bad">{setTreatment.error.message}</p>}
          <div><Button type="submit" disabled={!option || setTreatment.isPending}>Save treatment</Button></div>
        </form>
      ) : (
        <p className="text-[13px] text-fg-2">
          {risk.treatment.option ? TREATMENT_LABEL[risk.treatment.option] : risk.status === "draft" ? "Finish the assessment first." : "No treatment chosen yet."}
          {risk.treatment.note ? ` · ${risk.treatment.note}` : ""}
        </p>
      )}
      {risk.treatment.option === "modify" && <Actions risk={risk} />}
    </section>
  )
}

function Actions({ risk }: { risk: RiskDetail }) {
  const add = useAddAction(risk.code)
  const update = useUpdateTask(risk.code)
  const people = usePeople()
  const [title, setTitle] = useState("")
  const [assignee, setAssignee] = useState("")
  const [due, setDue] = useState("")

  async function submit(event: FormEvent) {
    event.preventDefault()
    await add.mutateAsync({ title: title.trim(), assignee_id: assignee || null, due: due || null })
    setTitle("")
    setAssignee("")
    setDue("")
  }

  return (
    <div className="grid gap-2 border-t border-line pt-3">
      <h3 className="text-[13.5px] font-semibold">
        Actions <span className="font-normal text-fg-3">{risk.progress.done} of {risk.progress.total} done</span>
      </h3>
      <ul className="grid gap-1.5">
        {risk.actions.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
            <span className="min-w-0">
              <span className="font-medium">{a.title}</span>
              <span className="text-fg-3"> · {a.assignee?.full_name ?? "Unassigned"}{a.due ? ` · due ${formatDate(a.due)}` : ""}</span>
            </span>
            {risk.can_edit ? (
              <select aria-label={`Status of ${a.title}`} value={a.status} className={input}
                onChange={(e) => update.mutate({ id: a.id, status: e.target.value })}>
                {Object.entries(TASK_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            ) : (
              <span className="text-fg-2">{TASK_STATUS_LABEL[a.status]}</span>
            )}
          </li>
        ))}
      </ul>
      {risk.can_edit && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <div className="grid min-w-48 flex-1 gap-1">
            <label htmlFor="action-title" className="text-[13px] font-medium">New action</label>
            <input id="action-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
          </div>
          <div className="grid gap-1">
            <label htmlFor="action-assignee" className="text-[13px] font-medium">Assignee</label>
            <select id="action-assignee" value={assignee} onChange={(e) => setAssignee(e.target.value)} className={input}>
              <option value="">Unassigned</option>
              {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select>
          </div>
          <div className="grid gap-1">
            <label htmlFor="action-due" className="text-[13px] font-medium">Due</label>
            <input id="action-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} />
          </div>
          <Button type="submit" variant="secondary" disabled={!title.trim() || add.isPending}>Add action</Button>
          {add.isError && <p role="alert" className="w-full text-[13px] text-bad">{add.error.message}</p>}
        </form>
      )}
    </div>
  )
}

function Acceptance({ risk }: { risk: RiskDetail }) {
  const accept = useAcceptRisk(risk.code)
  const [statement, setStatement] = useState("")
  const a = risk.acceptance
  const actionsOpen = risk.actions.some((t) => !["done", "cancelled"].includes(t.status))

  function submit(event: FormEvent) {
    event.preventDefault()
    accept.mutate(statement.trim())
  }

  let body
  if (a) {
    body = (
      <>
        <p className="text-[13px]">
          Accepted by {a.accepted_by ?? "unknown"} on {formatDate(a.accepted_at)}, valid until {formatDate(a.expires_at)}.
        </p>
        <blockquote className="border-l-2 border-line-2 pl-3 text-[13px] text-fg-2">{a.statement}</blockquote>
      </>
    )
  } else if (!risk.required_authority) {
    body = <p className="text-[13px] text-fg-3">Finish the assessment to decide on acceptance.</p>
  } else if (actionsOpen) {
    body = <p className="text-[13px] text-fg-3">Finish the treatment actions before accepting the residual risk.</p>
  } else if (risk.can_accept) {
    body = (
      <form onSubmit={submit} className="grid gap-2">
        <label htmlFor="acceptance-statement" className="text-[13px] font-medium">Acceptance statement</label>
        <textarea id="acceptance-statement" rows={3} value={statement} onChange={(e) => setStatement(e.target.value)} className={input} />
        {accept.isError && <p role="alert" className="text-[13px] text-bad">{accept.error.message}</p>}
        <div><Button type="submit" disabled={!statement.trim() || accept.isPending}>Accept residual risk</Button></div>
      </form>
    )
  } else {
    body = <p className="text-[13px] text-fg-2">Waiting for acceptance by {AUTHORITY_LABEL[risk.required_authority]}.</p>
  }
  return (
    <section className={`${card} grid gap-2`} aria-labelledby="acceptance-heading">
      <h2 id="acceptance-heading" className="text-[15px] font-semibold">Acceptance</h2>
      {body}
    </section>
  )
}

function History({ risk }: { risk: RiskDetail }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-[15px] font-semibold">Assessment history</h2>
      {risk.history.length === 0 ? (
        <p className="text-[13px] text-fg-3">Not assessed yet.</p>
      ) : (
        <ul className="grid gap-2">
          {risk.history.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
              <span className="text-fg-2">
                {a.finalized_at ? formatDate(a.finalized_at) : "—"} · {a.assessed_by ?? "unknown"} · methodology v{a.methodology_version}
              </span>
              <span className="flex items-center gap-1.5"><LevelPill level={a.inherent} /> → <LevelPill level={a.current} /></span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function CloseRisk({ risk }: { risk: RiskDetail }) {
  const close = useCloseRisk(risk.code)
  const [reason, setReason] = useState("")
  return (
    <details className={card}>
      <summary className="cursor-pointer text-[13px] font-medium">Close this risk</summary>
      <form onSubmit={(e) => { e.preventDefault(); close.mutate(reason.trim()) }} className="mt-3 grid gap-2">
        <label htmlFor="close-reason" className="text-[13px] font-medium">Why is it no longer relevant?</label>
        <textarea id="close-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
        {close.isError && <p role="alert" className="text-[13px] text-bad">{close.error.message}</p>}
        <div><Button type="submit" variant="secondary" disabled={!reason.trim() || close.isPending}>Close risk</Button></div>
      </form>
    </details>
  )
}

/** Choosing an owner is a draft; Save commits it, so arrowing through the list never reassigns the risk. */
function OwnerField({ risk }: { risk: RiskDetail }) {
  const update = useUpdateRisk(risk.code)
  const saved = risk.owner?.id ?? null
  const [draft, setDraft] = useState<string | null>(saved)
  const changed = draft !== saved
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span>Owner:</span>
      <OwnerPicker label="Risk owner" value={draft} current={risk.owner} onChange={setDraft} busy={update.isPending} />
      {changed && (
        <Button size="sm" onClick={() => update.mutate({ owner_id: draft })} disabled={update.isPending}>
          Save owner
        </Button>
      )}
      {update.isError && <span role="alert" className="text-bad">{update.error.message}</span>}
    </span>
  )
}
