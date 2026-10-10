import { type FormEvent, useState } from "react"
import {
  ASSET_TYPE_LABEL, type AssetInput, CLASSIFICATION_LABEL, LIFECYCLE_LABEL, useAssets, useCreateAsset, useUpdateAsset,
} from "../api/assets"
import { usePeople } from "../api/people"
import type { Asset } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"

const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const RATINGS = [1, 2, 3, 4, 5]

export function AssetsPage() {
  const me = useMe()
  const perms = me.data?.permissions ?? []
  const canManage = perms.includes("assets:write")
  const [showRetired, setShowRetired] = useState(false)
  const assets = useAssets(showRetired)
  const [editing, setEditing] = useState<Asset | "new" | null>(null)
  const canEdit = (asset: Asset) => canManage || (perms.includes("assets:write_own") && asset.owner?.id === me.data?.id)
  const rows = assets.data ?? []

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Risk</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Assets</h1>
        </div>
        <div className="flex items-center gap-3">
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
                <td className="min-w-48 px-3.5 py-2.5">{a.name}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{ASSET_TYPE_LABEL[a.type] ?? a.type}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{a.owner?.full_name ?? "Unassigned"}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{CLASSIFICATION_LABEL[a.classification] ?? a.classification}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums">{`${a.confidentiality} / ${a.integrity} / ${a.availability}`}</td>
                <td className="px-3.5 py-2.5 font-semibold tabular-nums">{a.criticality}</td>
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
  const error = create.error ?? update.error

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body: AssetInput = {
      name: name.trim(), type, classification, ...ratings,
      location: location.trim() || null, description: description.trim() || null, lifecycle,
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
              {RATINGS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        ))}
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
