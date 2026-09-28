import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { createPartnerCampaign, fetchPartnerCampaigns, safeColor, updatePartnerCampaign } from '../api/campaigns'
import type { PartnerCampaign } from '../types/campaign'
import type { PartnerProduct, PartnerStore } from '../types/partner'

type Props = {
  stores: PartnerStore[]
  products: PartnerProduct[]
}

const EMPTY = { name: '', description: '', accent_color: '#795b3d' }

export default function PartnerCampaigns({ stores, products }: Props) {
  const [campaigns, setCampaigns] = useState<PartnerCampaign[]>([])
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY)
  const [storeId, setStoreId] = useState<number | null>(stores[0]?.id ?? null)
  const [selected, setSelected] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchPartnerCampaigns(controller.signal)
      .then(setCampaigns)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError('Não foi possível carregar as vitrines.')
      })
    return () => controller.abort()
  }, [])

  const storeProducts = products.filter((p) => p.store === storeId)

  function toggleProduct(id: number) {
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]))
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (storeId === null) return
    setError(null)
    setSaving(true)
    try {
      const created = await createPartnerCampaign({ store: storeId, ...form, products: selected })
      setCampaigns((current) => [...current, created])
      setForm(EMPTY)
      setSelected([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível criar a vitrine.')
    } finally {
      setSaving(false)
    }
  }

  async function handleToggle(campaign: PartnerCampaign) {
    setError(null)
    try {
      const updated = await updatePartnerCampaign(campaign.id, { active: !campaign.active })
      setCampaigns((current) => current.map((c) => (c.id === updated.id ? updated : c)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível atualizar a vitrine.')
    }
  }

  return (
    <>
      {error && <p role="alert">{error}</p>}
      <table className="partner-table">
        <thead>
          <tr>
            <th>Vitrine</th>
            <th>Peças</th>
            <th>Situação</th>
            <th aria-label="Ações" />
          </tr>
        </thead>
        <tbody>
          {campaigns.length === 0 && (
            <tr>
              <td colSpan={4}>Nenhuma vitrine ainda.</td>
            </tr>
          )}
          {campaigns.map((campaign) => (
            <tr key={campaign.id}>
              <td>
                <span className="swatch" style={{ background: safeColor(campaign.accent_color) }} />{' '}
                {campaign.active ? <Link to={`/vitrines/${campaign.slug}`}>{campaign.name}</Link> : campaign.name}
              </td>
              <td>{campaign.products.length}</td>
              <td>{campaign.active ? 'No ar' : 'Pausada'}</td>
              <td className="partner-actions">
                <button type="button" onClick={() => handleToggle(campaign)}>
                  {campaign.active ? 'Pausar' : 'Publicar'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="partner-form" onSubmit={handleCreate}>
        <h2>Nova vitrine</h2>
        {stores.length > 1 && (
          <>
            <label htmlFor="c-store">Loja</label>
            <select
              id="c-store"
              value={storeId ?? ''}
              onChange={(e) => {
                setStoreId(Number(e.target.value))
                setSelected([])
              }}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </>
        )}
        <label htmlFor="c-name">Nome</label>
        <input
          id="c-name"
          maxLength={120}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <label htmlFor="c-desc">Texto de apresentação</label>
        <textarea id="c-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <label htmlFor="c-color">Cor de destaque</label>
        <input
          id="c-color"
          type="color"
          value={form.accent_color}
          onChange={(e) => setForm({ ...form, accent_color: e.target.value })}
        />
        <fieldset className="partner-checklist">
          <legend>Peças da vitrine</legend>
          {storeProducts.length === 0 && <span>Cadastre produtos na aba Produtos primeiro.</span>}
          {storeProducts.map((p) => (
            <label key={p.id}>
              <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleProduct(p.id)} /> {p.name}
            </label>
          ))}
        </fieldset>
        <button type="submit" disabled={saving}>
          {saving ? 'Salvando…' : 'Criar vitrine'}
        </button>
      </form>
    </>
  )
}
