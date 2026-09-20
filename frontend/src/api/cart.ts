import { apiFetch, ensureCsrfCookie } from './client'
import type { Cart } from '../types/cart'

export async function fetchCart(signal?: AbortSignal): Promise<Cart> {
  return apiFetch<Cart>('/api/v1/cart/', { signal })
}

export async function addCartItem(productId: number, quantity = 1): Promise<Cart> {
  await ensureCsrfCookie()
  return apiFetch<Cart>('/api/v1/cart/items/', {
    method: 'POST',
    body: JSON.stringify({ product_id: productId, quantity }),
  })
}

export async function updateCartItem(itemId: number, quantity: number): Promise<Cart> {
  await ensureCsrfCookie()
  return apiFetch<Cart>(`/api/v1/cart/items/${itemId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ quantity }),
  })
}

export async function removeCartItem(itemId: number): Promise<Cart> {
  await ensureCsrfCookie()
  return apiFetch<Cart>(`/api/v1/cart/items/${itemId}/`, { method: 'DELETE' })
}
