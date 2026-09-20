import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchOrders } from '../api/orders'
import type { Order } from '../types/order'

type LoadState = 'loading' | 'ready' | 'error'

export default function MyOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [state, setState] = useState<LoadState>('loading')

  useEffect(() => {
    const controller = new AbortController()

    fetchOrders(controller.signal)
      .then((data) => {
        setOrders(data)
        setState('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState('error')
      })

    return () => controller.abort()
  }, [])

  if (state === 'loading') {
    return <p>Carregando pedidos…</p>
  }

  if (state === 'error') {
    return <p role="alert">Não foi possível carregar seus pedidos.</p>
  }

  if (orders.length === 0) {
    return (
      <section aria-labelledby="orders-title">
        <h1 id="orders-title">Meus pedidos</h1>
        <p>Você ainda não fez nenhum pedido.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="orders-title">
      <h1 id="orders-title">Meus pedidos</h1>
      <ul className="order-list">
        {orders.map((order) => (
          <li key={order.id}>
            <Link to={`/pedidos/${order.id}`}>
              Pedido #{order.id} — {new Date(order.created_at).toLocaleDateString('pt-BR')} — R$ {order.total}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
