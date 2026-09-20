import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { addCartItem, fetchCart, removeCartItem, updateCartItem } from '../api/cart'
import { useAuth } from './AuthContext'
import type { Cart } from '../types/cart'

type CartContextValue = {
  cart: Cart | null
  loading: boolean
  itemCount: number
  addItem: (productId: number, quantity?: number) => Promise<void>
  updateItem: (itemId: number, quantity: number) => Promise<void>
  removeItem: (itemId: number) => Promise<void>
  clear: () => void
}

const CartContext = createContext<CartContextValue | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [cart, setCart] = useState<Cart | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setCart(await fetchCart())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user) {
      refresh().catch(() => setCart(null))
    } else {
      setCart(null)
    }
  }, [user, refresh])

  const addItem = useCallback(async (productId: number, quantity = 1) => {
    setCart(await addCartItem(productId, quantity))
  }, [])

  const updateItem = useCallback(async (itemId: number, quantity: number) => {
    setCart(await updateCartItem(itemId, quantity))
  }, [])

  const removeItem = useCallback(async (itemId: number) => {
    setCart(await removeCartItem(itemId))
  }, [])

  const clear = useCallback(() => setCart(null), [])

  const itemCount = cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0

  return (
    <CartContext.Provider value={{ cart, loading, itemCount, addItem, updateItem, removeItem, clear }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext)
  if (!context) {
    throw new Error('useCart deve ser usado dentro de CartProvider.')
  }
  return context
}
