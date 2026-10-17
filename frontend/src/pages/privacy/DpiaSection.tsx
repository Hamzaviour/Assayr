import { type FormEvent, useEffect, useState } from "react"
import { ApiError } from "../../api/client"
import {
  type Dpia,
  SCREENING,
  useAddDpiaRisk,
  useDpia,
  useDpiaAction,
  useRaiseDpiaRisk,
  useRemoveDpiaRisk,
  useSaveDpia,
} from "../../api/privacy2"
import { Button } from "../../components/Button"
import { LEVEL_COLOR, LEVEL_LABEL } from "../../components/LevelBadge"
import { formatDate } from "../../lib/format"
import { Tag } from "../Privacy"

const CARD = "rounded-2xl border border-line bg-surface p-5"
const FIELD = "w-full rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13.5px] text-fg"
const LABEL = "grid gap-1 text-[12.5px] font-medium text-fg-2"
const DECISIVE = new Set(["sensitive", "children", "automated"])
const STATUS: Record<Dpia["status"], [string, string]> = {
  draft: ["Draft", "bg-transparent text-fg-2 border-line-2 border-dashed"],
  in_review: ["In review", "bg-review-soft text-review border-review/25"],
  approved: ["Approved", "bg-ok-soft text-ok border-ok/25"],
}

const recommended = (answers: Record<string, boolean>) => {
  const yes = Object.keys(answers).filter((k) => answers[k])
  return yes.some((k) => DECISIVE.has(k)) || yes.length >= 2
}

/** A likelihood × impact score in the colour of its level (Very low grey … Very high red). */
function ScoreCell({ id, score, level, label }: { id: string; score: number; level: number; label: string }) {
  const color = LEVEL_COLOR[level]
  return (
    <span
      data-testid={id}
      title={label}
      className="inline-grid min-w-9 place-items-center rounded-lg px-2 py-1 text-[13px] font-bold tabular-nums"
      style={{ color, background: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      {score}
    </span>
  )
}

function Screening({ answers, onChange, disabled }: { answers: Record<string, boolean>; onChange: (a: Record<string, boolean>) => void; disabled: boolean }) {
  return (
    <fieldset className="grid gap-2" disabled={disabled}>
      <legend className="mb-1 text-[13px] font-semibold">Screening — does this processing involve…</legend>
      <div className="grid gap-1.5 md:grid-cols-2">
        {Object.entries(SCREENING).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
            <input type="checkbox" checked={!!answers[key]} onChange={(e) => onChange({ ...answers, [key]: e.target.checked })} />
            {label}
          </label>
        ))}
      </div>
      <p className={`text-[13px] font-medium ${recommended(answers) ? "text-warn" : "text-fg-3"}`}>
        {recommended(answers) ? "A DPIA is recommended for this activity." : "A DPIA is not required on these answers, but you may still carry one out."}
      </p>
    </fieldset>
  )
}

function Rating({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return (
    <label className={LABEL}>
      {label}
      <select value={value} onChange={(e) => onChange(Number(e.target.value))} className={FIELD}>
        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} · {LEVEL_LABEL[n]}</option>)}
      </select>
    </label>
  )
}

function Assessment({ activityId, dpia }: { activityId: string; dpia: Dpia }) {
  const save = useSaveDpia(activityId)
  const action = useDpiaAction(activityId)
  const addRisk = useAddDpiaRisk(activityId)
  const removeRisk = useRemoveDpiaRisk(activityId)
  const raise = useRaiseDpiaRisk(activityId)
  const locked = dpia.status === "approved" || !dpia.can_edit
  const [text, setText] = useState({ description: dpia.description ?? "", necessity: dpia.necessity ?? "", consultation: dpia.consultation ?? "", conclusion: dpia.conclusion ?? "" })
  const [risk, setRisk] = useState({ title: "", likelihood: 3, impact: 3, measures: "", residual_likelihood: 2, residual_impact: 2 })
  useEffect(() => {
    setText({ description: dpia.description ?? "", necessity: dpia.necessity ?? "", consultation: dpia.consultation ?? "", conclusion: dpia.conclusion ?? "" })
  }, [dpia.description, dpia.necessity, dpia.consultation, dpia.conclusion])
  const error = save.error ?? action.error ?? addRisk.error ?? raise.error ?? removeRisk.error

  function onAddRisk(event: FormEvent) {
    event.preventDefault()
    addRisk.mutate(
      { ...risk, title: risk.title.trim(), measures: risk.measures.trim() || null },
      { onSuccess: () => setRisk({ title: "", likelihood: 3, impact: 3, measures: "", residual_likelihood: 2, residual_impact: 2 }) },
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tag tone={STATUS[dpia.status][1]}>{STATUS[dpia.status][0]}</Tag>
        {dpia.approved_by && dpia.approved_at && (
          <span className="text-[12.5px] text-fg-2">Approved by {dpia.approved_by.full_name} on {formatDate(dpia.approved_at)}</span>
        )}
      </div>
      <Screening answers={dpia.screening} onChange={(screening) => save.mutate({ screening })} disabled={locked} />
      <div className="grid gap-3 md:grid-cols-2">
        {(
          [
            ["description", "Description of the processing"],
            ["necessity", "Necessity and proportionality"],
            ["consultation", "Consultation (people affected, IT, legal)"],
            ["conclusion", "Conclusion"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className={LABEL}>
            {label}
            <textarea
              rows={3}
              disabled={locked}
              value={text[key]}
              onChange={(e) => setText({ ...text, [key]: e.target.value })}
              onBlur={() => text[key] !== (dpia[key] ?? "") && save.mutate({ [key]: text[key] || null })}
              className={FIELD}
            />
          </label>
        ))}
      </div>
      <div className="grid gap-2">
        <h3 className="text-[14px] font-semibold">Privacy risks</h3>
        {dpia.risks.length === 0 ? (
          <p className="text-[13px] text-fg-3">No risks recorded yet.</p>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-fg-3">
                {["Risk", "L × I", "Measures", "Residual", ""].map((h) => <th key={h} className="px-2 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {dpia.risks.map((r) => (
                <tr key={r.id} className="border-t border-line align-top">
                  <td className="px-2 py-2 font-medium">{r.title}</td>
                  <td className="whitespace-nowrap px-2 py-2">
                    <span className="mr-1.5 text-[12px] text-fg-3">{r.likelihood} × {r.impact}</span>
                    <ScoreCell id={`score-${r.id}`} score={r.score} level={r.level} label={r.level_label} />
                  </td>
                  <td className="px-2 py-2 text-fg-2">{r.measures ?? "—"}</td>
                  <td className="px-2 py-2 text-fg-2">{r.residual_score ? `${r.residual_score} · ${r.residual_level_label}` : "—"}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-right">
                    {r.risk ? (
                      <span className="text-[12px] font-semibold text-primary">In register: {r.risk.code}</span>
                    ) : (
                      dpia.can_edit && (
                        <Button size="sm" variant="ghost" aria-label={`Add ${r.title} to the risk register`} onClick={() => raise.mutate(r.id)}>
                          To risk register
                        </Button>
                      )
                    )}
                    {!locked && (
                      <button type="button" aria-label={`Remove ${r.title}`} onClick={() => removeRisk.mutate(r.id)} className="ml-1 rounded px-1.5 text-fg-3 hover:text-bad">
                        ×
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!locked && (
          <form onSubmit={onAddRisk} className="grid gap-2 rounded-xl border border-line p-3 md:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto] md:items-end">
            <label className={LABEL}>
              Risk
              <input value={risk.title} onChange={(e) => setRisk({ ...risk, title: e.target.value })} maxLength={300} className={FIELD} />
            </label>
            <Rating label="Likelihood" value={risk.likelihood} onChange={(n) => setRisk({ ...risk, likelihood: n })} />
            <Rating label="Impact" value={risk.impact} onChange={(n) => setRisk({ ...risk, impact: n })} />
            <Rating label="Residual likelihood" value={risk.residual_likelihood} onChange={(n) => setRisk({ ...risk, residual_likelihood: n })} />
            <Rating label="Residual impact" value={risk.residual_impact} onChange={(n) => setRisk({ ...risk, residual_impact: n })} />
            <Button type="submit" size="sm" variant="secondary" disabled={!risk.title.trim() || addRisk.isPending}>Add risk</Button>
            <label className={`${LABEL} md:col-span-6`}>
              Measures
              <input value={risk.measures} onChange={(e) => setRisk({ ...risk, measures: e.target.value })} maxLength={5000} className={FIELD} />
            </label>
          </form>
        )}
      </div>
      {dpia.can_edit && (
        <div className="flex flex-wrap gap-2">
          {dpia.status === "draft" && <Button size="sm" variant="secondary" onClick={() => action.mutate("submit")}>Submit for review</Button>}
          {dpia.status !== "approved" && <Button size="sm" onClick={() => action.mutate("approve")}>Approve DPIA</Button>}
          {dpia.status === "approved" && <Button size="sm" variant="secondary" onClick={() => action.mutate("reopen")}>Reopen</Button>}
        </div>
      )}
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
    </div>
  )
}

export function DpiaSection({ activityId, canEdit }: { activityId: string; canEdit: boolean }) {
  const dpia = useDpia(activityId)
  const save = useSaveDpia(activityId)
  const [answers, setAnswers] = useState<Record<string, boolean>>({})
  const missing = dpia.isError && dpia.error instanceof ApiError && dpia.error.status === 404

  return (
    <section aria-label="Data protection impact assessment" className={`${CARD} grid gap-4`}>
      <h2 className="text-[15px] font-semibold">Data protection impact assessment</h2>
      {dpia.isPending && <p role="status" className="text-[13px] text-fg-3">Loading…</p>}
      {dpia.data && <Assessment activityId={activityId} dpia={dpia.data} />}
      {missing && (
        <>
          <Screening answers={answers} onChange={setAnswers} disabled={!canEdit} />
          {canEdit && (
            <div>
              <Button size="sm" disabled={save.isPending} onClick={() => save.mutate({ screening: answers })}>Start DPIA</Button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
