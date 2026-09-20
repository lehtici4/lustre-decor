import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createOrder } from '../api/orders'
import { useCart } from '../context/CartContext'

export default function CartPage() {
  const { cart, loading, updateItem, removeItem, clear } = useCart()
  const [checkingOut, setCheckingOut] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleCheckout() {
    setError(null)
    setCheckingOut(true)
    try {
      const order = await createOrder()
      clear()
      navigate(`/pedidos/${order.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível registrar o pedido.')
    } finally {
      setCheckingOut(false)
    }
  }

  if (loading && !cart) {
    return <p>Carregando carrinho…</p>
  }

  if (!cart || cart.items.length === 0) {
    return (
      <section aria-labelledby="cart-title">
        <h1 id="cart-title">Carrinho</h1>
        <p>Seu carrinho está vazio.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="cart-title">
      <h1 id="cart-title">Carrinho</h1>
      <ul className="cart-list">
        {cart.items.map((item) => (
          <li key={item.id} className="cart-item">
            <span className="cart-item-name">{item.product_name}</span>
            <span>R$ {item.unit_price}</span>
            <input
              type="number"
              min={1}
              value={item.quantity}
              aria-label={`Quantidade de ${item.product_name}`}
              onChange={(event) => {
                const quantity = Number(event.target.value)
                if (quantity >= 1) updateItem(item.id, quantity)
              }}
            />
            <span>R$ {item.subtotal}</span>
            <button type="button" onClick={() => removeItem(item.id)}>
              Remover
            </button>
          </li>
        ))}
      </ul>
      <p className="cart-total">Total: R$ {cart.total}</p>
      {error && <p role="alert">{error}</p>}
      <button type="button" onClick={handleCheckout} disabled={checkingOut}>
        {checkingOut ? 'Registrando pedido…' : 'Finalizar pedido'}
      </button>
    </section>
  )
}
