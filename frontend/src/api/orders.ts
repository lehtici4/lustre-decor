import { apiFetch, ensureCsrfCookie } from './client'
import type { Order } from '../types/order'

export async function fetchOrders(signal?: AbortSignal): Promise<Order[]> {
  return apiFetch<Order[]>('/api/v1/orders/', { signal })
}

export async function fetchOrder(id: string, signal?: AbortSignal): Promise<Order> {
  return apiFetch<Order>(`/api/v1/orders/${id}/`, { signal })
}

export async function createOrder(): Promise<Order> {
  await ensureCsrfCookie()
  return apiFetch<Order>('/api/v1/orders/', { method: 'POST' })
}
