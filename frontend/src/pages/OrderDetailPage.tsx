import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchOrder } from '../api/orders'
import type { Order } from '../types/order'

type LoadState = 'loading' | 'ready' | 'not-found' | 'error'

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [order, setOrder] = useState<Order | null>(null)
  const [state, setState] = useState<LoadState>('loading')

  useEffect(() => {
    if (!id) return

    const controller = new AbortController()
    setState('loading')

    fetchOrder(id, controller.signal)
      .then((data) => {
        setOrder(data)
        setState('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState('error')
      })

    return () => controller.abort()
  }, [id])

  if (state === 'loading') {
    return <p>Carregando pedido…</p>
  }

  if (state === 'error' || !order) {
    return (
      <p role="alert">
        Pedido não encontrado. <Link to="/pedidos">Ver meus pedidos</Link>
      </p>
    )
  }

  return (
    <section aria-labelledby="order-title">
      <h1 id="order-title">Pedido #{order.id}</h1>
      <p>Status: {order.status}</p>
      <p>Criado em: {new Date(order.created_at).toLocaleString('pt-BR')}</p>
      <ul className="cart-list">
        {order.items.map((item) => (
          <li key={item.id} className="cart-item">
            <span className="cart-item-name">{item.product_name}</span>
            <span>R$ {item.unit_price}</span>
            <span>x{item.quantity}</span>
          </li>
        ))}
      </ul>
      <p className="cart-total">Total: R$ {order.total}</p>
      <p>
        <Link to="/pedidos">Ver meus pedidos</Link> · <Link to="/catalogo">Voltar ao catálogo</Link>
      </p>
    </section>
  )
}
