import { type FormEvent, useState } from "react"
import {
  ASSET_TYPE_LABEL, type AssetInput, CLASSIFICATION_LABEL, LIFECYCLE_LABEL, useAssets, useCreateAsset, useUpdateAsset,
} from "../api/assets"
import { usePeople } from "../api/people"
import type { Asset } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { LEVEL_COLOR, LEVEL_LABEL, LevelBadge } from "../components/LevelBadge"
import { PII_CATEGORIES, PII_VOLUME, SENSITIVE } from "../lib/privacy"
import { StatusBar } from "../components/StatusBar"

const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const RATINGS = [1, 2, 3, 4, 5]
const word = (n: number) => LEVEL_LABEL[n] ?? String(n)

export function AssetsPage() {
  const me = useMe()
  const perms = me.data?.permissions ?? []
  const canManage = perms.includes("assets:write")
  const [showRetired, setShowRetired] = useState(false)
  const [minimum, setMinimum] = useState(0)
  const [piiOnly, setPiiOnly] = useState(false)
  const assets = useAssets(showRetired, { criticality: minimum || undefined, pii: piiOnly || undefined })
  const [editing, setEditing] = useState<Asset | "new" | null>(null)
  const canEdit = (asset: Asset) => canManage || (perms.includes("assets:write_own") && asset.owner?.id === me.data?.id)
  const all = assets.data ?? []
  const [level, setLevel] = useState<string | null>(null)
  const rows = level ? all.filter((a) => String(a.criticality) === level) : all

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Risk</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Assets</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[13px]">
            Criticality
            <select value={minimum} onChange={(e) => setMinimum(Number(e.target.value))} className="rounded-lg border border-line-2 bg-surface px-2 py-1 text-[13px]">
              <option value={0}>All</option>
              {[2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{word(n)}{n < 5 ? " and above" : ""}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={piiOnly} onChange={(e) => setPiiOnly(e.target.checked)} />
            Only assets with personal data
          </label>
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} />
            Show retired
          </label>
          {canManage && !editing && <Button onClick={() => setEditing("new")}>Add asset</Button>}
        </div>
      </header>
      {editing && (
        <AssetForm key={editing === "new" ? "new" : editing.id} asset={editing === "new" ? null : editing}
          canChangeOwner={canManage} onDone={() => setEditing(null)} />
      )}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        {all.length > 0 && (
          <div className="border-b border-line px-3.5 py-3">
            <StatusBar
              label="Assets by criticality"
              selected={level}
              onSelect={setLevel}
              segments={[1, 2, 3, 4, 5].map((n) => ({
                key: String(n),
                label: LEVEL_LABEL[n],
                color: LEVEL_COLOR[n],
                value: all.filter((a) => a.criticality === n).length,
              }))}
            />
          </div>
        )}
        {assets.isError && <p role="alert" className="p-4">{assets.error.message}</p>}
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["ID", "Name", "Type", "Owner", "Classification", "C / I / A", "Criticality", "Lifecycle", ""].map((h, i) => (
                <th key={i} className="px-3.5 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id} className="border-t border-line hover:bg-subtle">
                <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[12.5px] text-fg-3">{a.code}</td>
                <td className="min-w-48 px-3.5 py-2.5">
                  {a.name}
                  {a.holds_pii && (
                    <span
                      title={(a.pii_categories ?? []).map((c) => PII_CATEGORIES[c] ?? c).join(", ")}
                      className={`ml-2 rounded-full px-1.5 py-0.5 text-[10.5px] font-bold ${a.pii_sensitive ? "bg-bad-soft text-bad" : "bg-primary-soft text-primary"}`}
                    >
                      PII{a.pii_sensitive ? " · sensitive" : ""}
                    </span>
                  )}
                </td>
                <td className="px-3.5 py-2.5 text-fg-2">{ASSET_TYPE_LABEL[a.type] ?? a.type}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{a.owner?.full_name ?? "Unassigned"}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{CLASSIFICATION_LABEL[a.classification] ?? a.classification}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-[12.5px] text-fg-2">
                  {`${word(a.confidentiality)} / ${word(a.integrity)} / ${word(a.availability)}`}
                </td>
                <td className="px-3.5 py-2.5"><LevelBadge level={a.criticality} testId={`criticality-${a.code}`} /></td>
                <td className="px-3.5 py-2.5 text-fg-2">{LIFECYCLE_LABEL[a.lifecycle] ?? a.lifecycle}</td>
                <td className="px-3.5 py-2.5 text-right">
                  {canEdit(a) && (
                    <Button variant="ghost" size="sm" aria-label={`Edit ${a.code}`} onClick={() => setEditing(a)}>Edit</Button>
                  )}
                </td>
              </tr>
            ))}
            {assets.isSuccess && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3.5 py-8 text-center text-fg-3">
                  No assets yet. Add the information, systems and services in scope.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}

function AssetForm({ asset, canChangeOwner, onDone }: { asset: Asset | null; canChangeOwner: boolean; onDone: () => void }) {
  const people = usePeople()
  const create = useCreateAsset()
  const update = useUpdateAsset()
  const [name, setName] = useState(asset?.name ?? "")
  const [type, setType] = useState(asset?.type ?? "information")
  const [owner, setOwner] = useState(asset?.owner?.id ?? "")
  const [classification, setClassification] = useState(asset?.classification ?? "internal")
  const [ratings, setRatings] = useState({
    confidentiality: asset?.confidentiality ?? 3,
    integrity: asset?.integrity ?? 3,
    availability: asset?.availability ?? 3,
  })
  const [location, setLocation] = useState(asset?.location ?? "")
  const [description, setDescription] = useState(asset?.description ?? "")
  const [lifecycle, setLifecycle] = useState(asset?.lifecycle ?? "in_use")
  const [holdsPii, setHoldsPii] = useState(asset?.holds_pii ?? false)
  const [categories, setCategories] = useState<string[]>(asset?.pii_categories ?? [])
  const [sensitiveChoice, setSensitiveChoice] = useState(asset?.pii_sensitive ?? false)
  const [volume, setVolume] = useState(asset?.pii_volume ?? "")
  const forcedSensitive = categories.some((c) => SENSITIVE.has(c))
  const sensitive = holdsPii && (forcedSensitive || sensitiveChoice)
  const criticality = Math.max(ratings.confidentiality, ratings.integrity, ratings.availability)
  const error = create.error ?? update.error

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body: AssetInput = {
      name: name.trim(), type, classification, ...ratings,
      location: location.trim() || null, description: description.trim() || null, lifecycle,
      holds_pii: holdsPii, pii_categories: holdsPii ? categories : [], pii_sensitive: sensitive,
      pii_volume: holdsPii && volume ? volume : null,
    }
    if (canChangeOwner) body.owner_id = owner || null
    if (asset) await update.mutateAsync({ id: asset.id, ...body })
    else await create.mutateAsync({ owner_id: null, ...body })
    onDone()
  }

  const select = (id: string, label: string, value: string, onChange: (v: string) => void, options: Record<string, string>, disabled = false) => (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-[13px] font-medium">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} className={input}>
        {Object.entries(options).map(([key, text]) => <option key={key} value={key}>{text}</option>)}
      </select>
    </div>
  )

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold">{asset ? `Edit ${asset.code}` : "New asset"}</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="grid gap-1 md:col-span-2">
          <label htmlFor="asset-name" className="text-[13px] font-medium">Name</label>
          <input id="asset-name" value={name} onChange={(e) => setName(e.target.value)} className={input} />
        </div>
        {select("asset-type", "Type", type, setType, ASSET_TYPE_LABEL)}
        {select("asset-owner", "Owner", owner, setOwner,
          { "": "Unassigned", ...Object.fromEntries((people.data ?? []).map((p) => [p.id, p.full_name])) }, !canChangeOwner)}
        {select("asset-classification", "Classification", classification, setClassification, CLASSIFICATION_LABEL)}
        {select("asset-lifecycle", "Lifecycle", lifecycle, setLifecycle, LIFECYCLE_LABEL)}
        {(["confidentiality", "integrity", "availability"] as const).map((key) => (
          <div key={key} className="grid gap-1">
            <label htmlFor={`asset-${key}`} className="text-[13px] font-medium">{key.charAt(0).toUpperCase() + key.slice(1)}</label>
            <select id={`asset-${key}`} value={ratings[key]} className={input}
              onChange={(e) => setRatings((r) => ({ ...r, [key]: Number(e.target.value) }))}>
              {RATINGS.map((n) => <option key={n} value={n}>{word(n)}</option>)}
            </select>
          </div>
        ))}
        <p className="flex items-center gap-2 text-[13px] text-fg-2 md:col-span-3">
          Criticality (the highest of the three): <span data-testid="criticality-preview"><LevelBadge level={criticality} /></span>
        </p>
        <fieldset className="grid gap-3 rounded-lg border border-line p-3 md:col-span-3">
          <legend className="px-1 text-[13px] font-semibold">Personal data</legend>
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={holdsPii} onChange={(e) => setHoldsPii(e.target.checked)} />
            Holds personal data (PII)
          </label>
          {holdsPii && (
            <>
              <div className="flex flex-wrap gap-2">
                {Object.entries(PII_CATEGORIES).map(([code, text]) => (
                  <label
                    key={code}
                    className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12.5px] ${
                      categories.includes(code)
                        ? SENSITIVE.has(code)
                          ? "border-bad/40 bg-bad-soft text-bad"
                          : "border-primary/40 bg-primary-soft text-primary"
                        : "border-line text-fg-2"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={categories.includes(code)}
                      onChange={(e) => setCategories(e.target.checked ? [...categories, code] : categories.filter((c) => c !== code))}
                    />
                    {text}
                    {SENSITIVE.has(code) && <span aria-hidden="true" className="text-[10px] font-bold">●</span>}
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-4">
                <label className="flex items-center gap-2 text-[13px]">
                  <input
                    type="checkbox"
                    checked={sensitive}
                    disabled={forcedSensitive}
                    onChange={(e) => setSensitiveChoice(e.target.checked)}
                  />
                  Sensitive personal data
                </label>
                <div className="grid gap-1">
                  <label htmlFor="asset-pii-volume" className="text-[13px] font-medium">Number of people</label>
                  <select id="asset-pii-volume" value={volume} onChange={(e) => setVolume(e.target.value)} className={input}>
                    <option value="">Not known</option>
                    {Object.entries(PII_VOLUME).map(([key, text]) => <option key={key} value={key}>{text}</option>)}
                  </select>
                </div>
              </div>
              {forcedSensitive && (
                <p className="text-[12px] text-bad">
                  Health, biometric, children&apos;s, religious, criminal and ethnic data are sensitive under Qatar&apos;s PDPPL.
                </p>
              )}
            </>
          )}
        </fieldset>
        <div className="grid gap-1 md:col-span-3">
          <label htmlFor="asset-location" className="text-[13px] font-medium">Location</label>
          <input id="asset-location" value={location} onChange={(e) => setLocation(e.target.value)} className={input} />
        </div>
        <div className="grid gap-1 md:col-span-3">
          <label htmlFor="asset-description" className="text-[13px] font-medium">Description</label>
          <textarea id="asset-description" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className={input} />
        </div>
      </div>
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={!name.trim() || create.isPending || update.isPending}>Save asset</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}
