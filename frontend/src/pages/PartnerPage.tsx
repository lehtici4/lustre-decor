import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  createPartnerProduct,
  fetchPartnerOrderItems,
  fetchPartnerProducts,
  fetchPartnerStores,
  updateFulfillment,
  updatePartnerProduct,
} from '../api/partner'
import PartnerCampaigns from '../components/PartnerCampaigns'
import { useAuth } from '../context/AuthContext'
import type { PartnerOrderItem, PartnerProduct, PartnerStore } from '../types/partner'

type Tab = 'produtos' | 'pedidos' | 'vitrines'

const EMPTY_FORM = { name: '', description: '', price: '', image_url: '' }

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

export default function PartnerPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('produtos')
  const [stores, setStores] = useState<PartnerStore[]>([])
  const [products, setProducts] = useState<PartnerProduct[]>([])
  const [items, setItems] = useState<PartnerOrderItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [storeId, setStoreId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (signal?: AbortSignal) => {
    const [storeList, productList, itemList] = await Promise.all([
      fetchPartnerStores(signal),
      fetchPartnerProducts(signal),
      fetchPartnerOrderItems(signal),
    ])
    setStores(storeList)
    setProducts(productList)
    setItems(itemList)
    setStoreId((current) => current ?? storeList[0]?.id ?? null)
  }, [])

  useEffect(() => {
    if (!user?.is_partner) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    load(controller.signal)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorMessage(err, 'Não foi possível carregar o painel.'))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [user, load])

  if (!user?.is_partner) {
    return (
      <section>
        <h1>Painel do parceiro</h1>
        <p role="alert">Acesso restrito a lojas parceiras. Fale com a administração da Lustre Decor.</p>
      </section>
    )
  }

  if (loading) return <p>Carregando painel…</p>

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (storeId === null) return
    setError(null)
    setSaving(true)
    try {
      const created = await createPartnerProduct({
        store: storeId,
        name: form.name,
        description: form.description,
        price: form.price,
        image_url: form.image_url || undefined,
      })
      setProducts((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)))
      setForm(EMPTY_FORM)
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível cadastrar o produto.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleToggle(product: PartnerProduct) {
    setError(null)
    try {
      const updated = await updatePartnerProduct(product.id, { active: !product.active })
      setProducts((current) => current.map((p) => (p.id === updated.id ? updated : p)))
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível atualizar o produto.'))
    }
  }

  async function handlePrice(product: PartnerProduct) {
    const price = window.prompt(`Novo preço de "${product.name}" (ex.: 129.90)`, product.price)
    if (price === null || price === product.price) return
    setError(null)
    try {
      const updated = await updatePartnerProduct(product.id, { price })
      setProducts((current) => current.map((p) => (p.id === updated.id ? updated : p)))
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível atualizar o preço.'))
    }
  }

  async function handleShip(item: PartnerOrderItem) {
    setError(null)
    try {
      const updated = await updateFulfillment(item.id, 'shipped')
      setItems((current) => current.map((i) => (i.id === updated.id ? updated : i)))
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível atualizar o envio.'))
    }
  }

  const pending = items.filter((i) => i.fulfillment_status === 'pending').length

  return (
    <section className="partner-panel" aria-labelledby="partner-title">
      <h1 id="partner-title">Painel do parceiro</h1>
      <p className="partner-stores">
        {stores.length === 1 ? 'Loja: ' : 'Lojas: '}
        {stores.map((s) => s.name).join(', ')}
      </p>

      <div className="partner-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'produtos'} onClick={() => setTab('produtos')}>
          Produtos ({products.length})
        </button>
        <button type="button" role="tab" aria-selected={tab === 'pedidos'} onClick={() => setTab('pedidos')}>
          Pedidos {pending > 0 ? `(${pending} a enviar)` : ''}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'vitrines'} onClick={() => setTab('vitrines')}>
          Vitrines
        </button>
      </div>

      {error && <p role="alert">{error}</p>}

      {tab === 'vitrines' ? (
        <PartnerCampaigns stores={stores} products={products} />
      ) : tab === 'produtos' ? (
        <>
          <table className="partner-table">
            <thead>
              <tr>
                <th>Produto</th>
                {stores.length > 1 && <th>Loja</th>}
                <th>Preço</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {products.length === 0 && (
                <tr>
                  <td colSpan={5}>Nenhum produto cadastrado ainda.</td>
                </tr>
              )}
              {products.map((product) => (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  {stores.length > 1 && <td>{product.store_name}</td>}
                  <td>R$ {product.price}</td>
                  <td>{product.active ? 'No catálogo' : 'Oculto'}</td>
                  <td className="partner-actions">
                    <button type="button" onClick={() => handlePrice(product)}>
                      Preço
                    </button>
                    <button type="button" onClick={() => handleToggle(product)}>
                      {product.active ? 'Ocultar' : 'Publicar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <form className="partner-form" onSubmit={handleCreate}>
            <h2>Novo produto</h2>
            {stores.length > 1 && (
              <>
                <label htmlFor="p-store">Loja</label>
                <select id="p-store" value={storeId ?? ''} onChange={(e) => setStoreId(Number(e.target.value))}>
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </>
            )}
            <label htmlFor="p-name">Nome</label>
            <input
              id="p-name"
              value={form.name}
              maxLength={200}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <label htmlFor="p-desc">Descrição</label>
            <textarea
              id="p-desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <label htmlFor="p-price">Preço (R$)</label>
            <input
              id="p-price"
              inputMode="decimal"
              pattern="\d+(\.\d{1,2})?"
              placeholder="129.90"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              required
            />
            <label htmlFor="p-img">Imagem (caminho /... ou URL https://, opcional)</label>
            <input
              id="p-img"
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
            <button type="submit" disabled={saving}>
              {saving ? 'Salvando…' : 'Cadastrar produto'}
            </button>
          </form>
        </>
      ) : (
        <table className="partner-table">
          <thead>
            <tr>
              <th>Pedido</th>
              <th>Data</th>
              <th>Item</th>
              <th>Qtd.</th>
              <th>Envio</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={6}>Nenhum pedido com produtos da sua loja ainda.</td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.id}>
                <td>#{item.order_id}</td>
                <td>{new Date(item.order_created_at).toLocaleDateString('pt-BR')}</td>
                <td>{item.product_name}</td>
                <td>{item.quantity}</td>
                <td>{item.fulfillment_status === 'shipped' ? 'Enviado' : 'Aguardando envio'}</td>
                <td className="partner-actions">
                  {item.fulfillment_status === 'pending' && (
                    <button type="button" onClick={() => handleShip(item)}>
                      Marcar como enviado
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
