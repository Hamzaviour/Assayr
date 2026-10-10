import { Link, useNavigate, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useRef, useState } from "react"
import { useAssets } from "../api/assets"
import {
  useAllControls, useFinalizeAssessment, useMethodology, useRisk, useRiskLibrary, useSaveAssessment,
  useSetRiskControls, useUpdateRisk,
} from "../api/risks"
import type { Level, Methodology, RiskDetail } from "../api/types"
import { Button } from "../components/Button"
import { CodePicker } from "../components/CodePicker"
import { Heatmap } from "../components/Heatmap"
import { LevelPill } from "../components/LevelPill"
import { StatusPill } from "../components/StatusPill"

const STEPS = ["Scenario", "Assets", "Likelihood", "Consequence", "Controls", "Result"]
const SCALE = [1, 2, 3, 4, 5]
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const heading = "text-[17px] font-semibold"

export function levelFor(methodology: Methodology, likelihood: number, consequence: number): Level {
  const score = likelihood * consequence
  const band = methodology.bands.find((b) => score >= b.min && score <= b.max)!
  return { likelihood, consequence, score, band: band.key, band_label: band.label }
}

export function RiskWizardPage() {
  const { code } = useParams({ from: "/app/risks/$code/assess" })
  const risk = useRisk(code)
  const methodology = useMethodology()
  if (risk.isError) return <p role="alert">{risk.error.message}</p>
  if (methodology.isError) return <p role="alert">{methodology.error.message}</p>
  if (!risk.data || !methodology.data) return <p role="status" className="text-fg-3">Loading…</p>
  return <Wizard risk={risk.data} methodology={methodology.data} />
}

function Wizard({ risk, methodology }: { risk: RiskDetail; methodology: Methodology }) {
  const [step, setStep] = useState(0)
  const [liveLikelihood, setLiveLikelihood] = useState<number | null>(null)
  const [liveConsequence, setLiveConsequence] = useState<number | null>(null)
  const open = useSaveAssessment(risk.code)
  const opened = useRef(risk.draft !== null)
  useEffect(() => {
    if (!opened.current && risk.status !== "closed") {
      opened.current = true
      open.mutate({})
    }
  }, [open, risk.status])

  const draft = risk.draft
  if (!draft) {
    return open.isError ? <p role="alert">{open.error.message}</p> : <p role="status" className="text-fg-3">Opening the assessment…</p>
  }
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1))
  const back = () => setStep((s) => Math.max(s - 1, 0))
  const likelihood = liveLikelihood ?? draft.likelihood
  const consequence = liveConsequence ?? draft.inherent?.consequence ?? null
  const position = likelihood && consequence ? levelFor(methodology, likelihood, consequence) : null

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-display text-[24px] font-extrabold tracking-tight">Assess {risk.code} {risk.title}</h1>
        <p className="text-[13px] text-fg-3">
          Step {step + 1} of {STEPS.length} ·{" "}
          <Link to="/risks/$code" params={{ code: risk.code }} className="text-primary underline">Save and exit</Link>
        </p>
      </header>
      <ol aria-label="Steps" className="flex flex-wrap gap-1.5">
        {STEPS.map((name, index) => (
          <li key={name}>
            <button type="button" onClick={() => setStep(index)} aria-current={index === step ? "step" : undefined}
              className="rounded-full border border-line-2 px-3 py-1 text-[12.5px] font-medium text-fg-2 aria-[current=step]:border-primary aria-[current=step]:bg-primary-soft aria-[current=step]:text-primary">
              {index + 1} {name}
            </button>
          </li>
        ))}
      </ol>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_300px]">
        <section className="rounded-xl border border-line bg-surface p-5">
          {step === 0 && <ScenarioStep risk={risk} onDone={next} />}
          {step === 1 && <AssetsStep risk={risk} onDone={next} onBack={back} />}
          {step === 2 && (
            <LikelihoodStep risk={risk} methodology={methodology} onLive={setLiveLikelihood} onDone={next} onBack={back} />
          )}
          {step === 3 && (
            <ConsequenceStep risk={risk} methodology={methodology} onLive={setLiveConsequence} onDone={next} onBack={back} />
          )}
          {step === 4 && <ControlsStep risk={risk} onDone={next} onBack={back} />}
          {step === 5 && <ResultStep risk={risk} methodology={methodology} onBack={back} />}
        </section>
        <LivePanel methodology={methodology} position={position} suggested={draft.suggested} />
      </div>
    </div>
  )
}

function StepButtons({ onBack, disabled, label = "Continue" }: { onBack?: () => void; disabled: boolean; label?: string }) {
  return (
    <div className="flex justify-between gap-2 border-t border-line pt-4">
      {onBack ? <Button type="button" variant="ghost" onClick={onBack}>Back</Button> : <span />}
      <Button type="submit" disabled={disabled}>{label}</Button>
    </div>
  )
}

function Failure({ error }: { error: Error | null }) {
  return error ? <p role="alert" className="text-[13px] text-bad">{error.message}</p> : null
}

function ScenarioStep({ risk, onDone }: { risk: RiskDetail; onDone: () => void }) {
  const library = useRiskLibrary()
  const update = useUpdateRisk(risk.code)
  const [title, setTitle] = useState(risk.title)
  const [description, setDescription] = useState(risk.description ?? "")
  const [category, setCategory] = useState(risk.category ?? "")
  const [approach, setApproach] = useState(risk.approach)
  const [threats, setThreats] = useState(risk.threats.map((t) => t.code))
  const [vulnerabilities, setVulnerabilities] = useState(risk.vulnerabilities.map((v) => v.code))

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({
      title: title.trim(),
      description: description.trim() || null,
      category: category.trim() || null,
      approach,
      threat_codes: threats,
      vulnerability_codes: vulnerabilities,
    })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>What could happen?</h2>
      <div className="grid gap-1">
        <label htmlFor="scenario-title" className="text-[13px] font-medium">Title</label>
        <input id="scenario-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
      </div>
      <div className="grid gap-1">
        <label htmlFor="scenario-text" className="text-[13px] font-medium">Scenario</label>
        <textarea id="scenario-text" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} className={input}
          placeholder="If … happens, then … because …" />
      </div>
      <div className="flex flex-wrap gap-4">
        <div className="grid gap-1">
          <label htmlFor="scenario-category" className="text-[13px] font-medium">Category</label>
          <input id="scenario-category" value={category} onChange={(e) => setCategory(e.target.value)} className={input} />
        </div>
        <fieldset className="grid gap-1">
          <legend className="text-[13px] font-medium">Approach</legend>
          <div className="flex gap-3 pt-1 text-[13px]">
            {[["event", "Event-based"], ["asset", "Asset-based"]].map(([value, label]) => (
              <label key={value} className="flex items-center gap-1.5">
                <input type="radio" name="approach" value={value} checked={approach === value} onChange={() => setApproach(value)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <CodePicker label="Threats" items={library.data?.threats ?? []} selected={threats} onChange={setThreats} />
        <CodePicker label="Vulnerabilities" items={library.data?.vulnerabilities ?? []} selected={vulnerabilities} onChange={setVulnerabilities} />
      </div>
      <Failure error={update.error} />
      <StepButtons disabled={!title.trim() || update.isPending} />
    </form>
  )
}

function AssetsStep({ risk, onDone, onBack }: { risk: RiskDetail; onDone: () => void; onBack: () => void }) {
  const assets = useAssets()
  const update = useUpdateRisk(risk.code)
  const [selected, setSelected] = useState(risk.assets.map((a) => a.id))
  const list = assets.data ?? []

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({ asset_ids: selected })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>Which assets are affected?</h2>
      <p className="text-[13px] text-fg-2">
        {risk.approach === "asset" ? "Asset-based risks start from the assets they affect." : "Optional for event-based risks."}
      </p>
      {list.length === 0 ? (
        <p className="text-[13px] text-fg-3">No assets in the inventory yet.</p>
      ) : (
        <div className="grid max-h-72 gap-1 overflow-y-auto rounded-lg border border-line p-2">
          {list.map((a) => (
            <label key={a.id} className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={selected.includes(a.id)}
                onChange={() => setSelected((s) => (s.includes(a.id) ? s.filter((x) => x !== a.id) : [...s, a.id]))} />
              <span className="font-mono text-fg-3">{a.code}</span> {a.name}
              <span className="text-fg-3">· criticality {a.criticality}</span>
            </label>
          ))}
        </div>
      )}
      <Failure error={update.error} />
      <StepButtons onBack={onBack} disabled={update.isPending} />
    </form>
  )
}

function LikelihoodStep({ risk, methodology, onLive, onDone, onBack }: {
  risk: RiskDetail
  methodology: Methodology
  onLive: (likelihood: number) => void
  onDone: () => void
  onBack: () => void
}) {
  const save = useSaveAssessment(risk.code)
  const [value, setValue] = useState<number | null>(risk.draft?.likelihood ?? null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({ likelihood: value })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>How likely is it to happen?</h2>
      <fieldset className="grid gap-2">
        <legend className="sr-only">Likelihood</legend>
        {methodology.likelihood.map((option) => (
          <div key={option.level} className="flex flex-wrap items-center gap-3 rounded-lg border border-line px-3 py-2">
            <input type="radio" id={`likelihood-${option.level}`} name="likelihood" checked={value === option.level}
              aria-describedby={`likelihood-${option.level}-help`}
              onChange={() => { setValue(option.level); onLive(option.level) }} />
            <label htmlFor={`likelihood-${option.level}`} className="text-[13.5px] font-medium">
              {`${option.level} · ${option.label}`}
            </label>
            <span id={`likelihood-${option.level}-help`} className="ml-auto text-[12.5px] text-fg-3">{option.guidance}</span>
          </div>
        ))}
      </fieldset>
      <Failure error={save.error} />
      <StepButtons onBack={onBack} disabled={value === null || save.isPending} />
    </form>
  )
}

function ConsequenceStep({ risk, methodology, onLive, onDone, onBack }: {
  risk: RiskDetail
  methodology: Methodology
  onLive: (consequence: number | null) => void
  onDone: () => void
  onBack: () => void
}) {
  const save = useSaveAssessment(risk.code)
  const dimensions = methodology.consequence.dimensions
  const [ratings, setRatings] = useState<Record<string, number>>(risk.draft?.consequence ?? {})
  const highest = (values: Record<string, number>) =>
    dimensions.every((d) => values[d.key]) ? Math.max(...dimensions.map((d) => values[d.key])) : null
  const overall = highest(ratings)

  function rate(key: string, value: number) {
    const updated = { ...ratings, [key]: value }
    setRatings(updated)
    onLive(highest(updated))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({ consequence: ratings })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>How bad would it be? Rate each area.</h2>
      <div className="grid gap-3">
        {dimensions.map((d) => (
          <div key={d.key} role="radiogroup" aria-label={d.label} className="grid gap-1 sm:grid-cols-[160px_auto_minmax(0,1fr)] sm:items-center">
            <span className="text-[13.5px] font-medium">{d.label}</span>
            <span className="flex gap-2">
              {SCALE.map((n) => (
                <input key={n} type="radio" name={`consequence-${d.key}`} aria-label={`${d.label} ${n}`} title={d.guidance[n - 1]}
                  checked={ratings[d.key] === n} onChange={() => rate(d.key, n)} />
              ))}
            </span>
            <span className="text-[12.5px] text-fg-3">{ratings[d.key] ? d.guidance[ratings[d.key] - 1] : "Not rated"}</span>
          </div>
        ))}
      </div>
      <p className="text-[13px] font-medium">
        {overall
          ? `Overall consequence = highest = ${overall} (${methodology.consequence.levels[overall - 1].label})`
          : "Rate every area to see the overall consequence."}
      </p>
      <Failure error={save.error} />
      <StepButtons onBack={onBack} disabled={overall === null || save.isPending} />
    </form>
  )
}

function ControlsStep({ risk, onDone, onBack }: { risk: RiskDetail; onDone: () => void; onBack: () => void }) {
  const controls = useAllControls()
  const setControls = useSetRiskControls(risk.code)
  const save = useSaveAssessment(risk.code)
  const draft = risk.draft!
  const suggested = draft.suggested
  const [links, setLinks] = useState(risk.controls.map((c) => ({ code: c.code, axis: c.axis })))
  const [adding, setAdding] = useState("")
  const [adjust, setAdjust] = useState(draft.current !== null)
  const [currentL, setCurrentL] = useState(draft.current?.likelihood ?? suggested?.likelihood ?? 1)
  const [currentC, setCurrentC] = useState(draft.current?.consequence ?? suggested?.consequence ?? 1)
  const [reason, setReason] = useState(draft.current_reason ?? "")
  const known = controls.data ?? []
  const info = (code: string) => known.find((c) => c.code === code) ?? risk.controls.find((c) => c.code === code)
  const addable = known.filter((c) => c.status !== "excluded" && !links.some((l) => l.code === c.code))

  async function submit(event: FormEvent) {
    event.preventDefault()
    await setControls.mutateAsync({ links })
    await save.mutateAsync(
      adjust
        ? { current_l: currentL, current_c: currentC, current_reason: reason.trim() || null }
        : { current_l: null, current_c: null, current_reason: null },
    )
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>Which controls already reduce this risk?</h2>
      <p className="text-[13px] text-fg-2">
        A compliant control lowers the risk by one level on the axis it affects; a control at risk counts for half; at most two levels per axis.
      </p>
      {links.length === 0 ? (
        <p className="text-[13px] text-fg-3">No controls linked yet.</p>
      ) : (
        <ul className="grid gap-2">
          {links.map((link) => {
            const control = info(link.code)
            return (
              <li key={link.code} className="flex flex-wrap items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
                <span className="font-mono text-fg-3">{link.code}</span>
                <span className="min-w-0 flex-1">{control?.title}</span>
                {control && <StatusPill status={control.status} />}
                <select aria-label={`Effect of ${link.code}`} value={link.axis} className={input}
                  onChange={(e) => setLinks((ls) => ls.map((l) => (l.code === link.code ? { ...l, axis: e.target.value } : l)))}>
                  <option value="likelihood">Reduces likelihood</option>
                  <option value="consequence">Reduces consequence</option>
                </select>
                <Button type="button" variant="ghost" size="sm" aria-label={`Remove ${link.code}`}
                  onClick={() => setLinks((ls) => ls.filter((l) => l.code !== link.code))}>
                  Remove
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-60 flex-1 gap-1">
          <label htmlFor="add-control" className="text-[13px] font-medium">Add a mitigating control</label>
          <select id="add-control" value={adding} onChange={(e) => setAdding(e.target.value)} className={input}>
            <option value="">Choose a control…</option>
            {addable.map((c) => <option key={c.code} value={c.code}>{c.code} {c.title}</option>)}
          </select>
        </div>
        <Button type="button" variant="secondary" disabled={!adding}
          onClick={() => { setLinks((ls) => [...ls, { code: adding, axis: "likelihood" }]); setAdding("") }}>
          Link control
        </Button>
      </div>
      <div className="grid gap-2 rounded-lg bg-subtle p-3 text-[13px]">
        <p className="flex flex-wrap items-center gap-2">
          Suggested current level <LevelPill level={suggested} />
          <span className="text-fg-3">Updates when you continue.</span>
        </p>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={adjust} onChange={(e) => setAdjust(e.target.checked)} />
          Adjust the current level
        </label>
        {adjust && (
          <div className="flex flex-wrap items-end gap-2">
            {([["Current likelihood", currentL, setCurrentL], ["Current consequence", currentC, setCurrentC]] as const).map(
              ([label, value, setter]) => (
                <div key={label} className="grid gap-1">
                  <label htmlFor={label.toLowerCase().replace(" ", "-")} className="font-medium">{label}</label>
                  <select id={label.toLowerCase().replace(" ", "-")} value={value} onChange={(e) => setter(Number(e.target.value))} className={input}>
                    {SCALE.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
              ),
            )}
            <div className="grid min-w-60 flex-1 gap-1">
              <label htmlFor="current-reason" className="font-medium">Why is it different from the suggestion?</label>
              <textarea id="current-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
            </div>
          </div>
        )}
      </div>
      <Failure error={setControls.error ?? save.error} />
      <StepButtons onBack={onBack} disabled={setControls.isPending || save.isPending} />
    </form>
  )
}

function ResultStep({ risk, methodology, onBack }: { risk: RiskDetail; methodology: Methodology; onBack: () => void }) {
  const save = useSaveAssessment(risk.code)
  const finalize = useFinalizeAssessment(risk.code)
  const navigate = useNavigate()
  const draft = risk.draft!
  const current = draft.current ?? draft.suggested
  const [setTarget, setSetTarget] = useState(draft.target !== null)
  const [targetL, setTargetL] = useState(draft.target?.likelihood ?? current?.likelihood ?? 1)
  const [targetC, setTargetC] = useState(draft.target?.consequence ?? current?.consequence ?? 1)
  const [rationale, setRationale] = useState(draft.rationale ?? "")
  const band = current ? methodology.bands.find((b) => b.key === current.band) : undefined

  async function finish(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({
      target_l: setTarget ? targetL : null,
      target_c: setTarget ? targetC : null,
      rationale: rationale.trim() || null,
    })
    await finalize.mutateAsync()
    navigate({ to: "/risks/$code", params: { code: risk.code } })
  }

  return (
    <form onSubmit={finish} className="grid gap-4">
      <h2 className={heading}>Result</h2>
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="text-fg-3">Inherent</span> <LevelPill level={draft.inherent} />
        <span aria-hidden="true">→</span>
        <span className="text-fg-3">{draft.current ? "Current (adjusted)" : "Current (suggested)"}</span> <LevelPill level={current} />
      </div>
      {band && (
        <p className={band.above_appetite ? "rounded-lg bg-warn-soft px-3 py-2 text-[13px]" : "text-[13px] text-fg-2"}>
          {`${band.above_appetite ? "Above appetite. " : ""}${band.rule}`}
        </p>
      )}
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={setTarget} onChange={(e) => setSetTarget(e.target.checked)} />
        Set a target level for after treatment
      </label>
      {setTarget && (
        <div className="flex flex-wrap gap-2 text-[13px]">
          {([["Target likelihood", targetL, setTargetL], ["Target consequence", targetC, setTargetC]] as const).map(
            ([label, value, setter]) => (
              <div key={label} className="grid gap-1">
                <label htmlFor={label.toLowerCase().replace(" ", "-")} className="font-medium">{label}</label>
                <select id={label.toLowerCase().replace(" ", "-")} value={value} onChange={(e) => setter(Number(e.target.value))} className={input}>
                  {SCALE.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            ),
          )}
        </div>
      )}
      <div className="grid gap-1">
        <label htmlFor="rationale" className="text-[13px] font-medium">Rationale</label>
        <textarea id="rationale" rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} className={input} />
      </div>
      <Failure error={save.error ?? finalize.error} />
      <StepButtons onBack={onBack} disabled={save.isPending || finalize.isPending || !current} label="Finish assessment" />
    </form>
  )
}

function LivePanel({ methodology, position, suggested }: {
  methodology: Methodology
  position: Level | null
  suggested: Level | null
}) {
  const band = position ? methodology.bands.find((b) => b.key === position.band) : undefined
  return (
    <aside aria-label="Live position" className="grid content-start gap-3 rounded-xl border border-line bg-surface p-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Live position</p>
      <Heatmap size="sm" points={[]} bands={methodology.bands} marker={position} />
      {position ? (
        <>
          <p className="text-[13px]">
            Inherent: L{position.likelihood} × C{position.consequence} = {position.score} · <b>{position.band_label}</b>
          </p>
          {band && (
            <p className={band.above_appetite ? "rounded-lg bg-warn-soft px-3 py-2 text-[13px]" : "text-[13px] text-fg-2"}>
              {`${band.above_appetite ? "Above appetite. " : ""}${band.rule}`}
            </p>
          )}
        </>
      ) : (
        <p className="text-[13px] text-fg-3">Rate the likelihood and every consequence area to see where this risk sits.</p>
      )}
      {suggested && (
        <p className="flex items-center gap-2 text-[13px]">Suggested current <LevelPill level={suggested} /></p>
      )}
    </aside>
  )
}
