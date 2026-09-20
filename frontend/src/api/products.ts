import { ApiError, apiFetch } from './client'
import type { Product } from '../types/product'

export async function fetchProducts(signal?: AbortSignal): Promise<Product[]> {
  return apiFetch<Product[]>('/api/v1/products/', { signal })
}

export async function fetchProduct(id: string, signal?: AbortSignal): Promise<Product> {
  try {
    return await apiFetch<Product>(`/api/v1/products/${id}/`, { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      throw new Error('Produto não encontrado.')
    }
    throw error
  }
}
