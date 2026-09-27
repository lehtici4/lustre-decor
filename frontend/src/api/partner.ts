import { apiFetch, ensureCsrfCookie } from './client'
import type {
  FulfillmentStatus,
  PartnerOrderItem,
  PartnerProduct,
  PartnerProductInput,
  PartnerStore,
} from '../types/partner'

// API do parceiro (marketplace). O backend só devolve dados das lojas do
// próprio parceiro — ver backend/apps/core/services/partner_service.py.

export function fetchPartnerStores(signal?: AbortSignal): Promise<PartnerStore[]> {
  return apiFetch<PartnerStore[]>('/api/v1/partner/stores/', { signal })
}

export function fetchPartnerProducts(signal?: AbortSignal): Promise<PartnerProduct[]> {
  return apiFetch<PartnerProduct[]>('/api/v1/partner/products/', { signal })
}

export async function createPartnerProduct(data: PartnerProductInput): Promise<PartnerProduct> {
  await ensureCsrfCookie()
  return apiFetch<PartnerProduct>('/api/v1/partner/products/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updatePartnerProduct(
  id: number,
  data: Partial<Pick<PartnerProduct, 'name' | 'description' | 'price' | 'active' | 'image_url'>>,
): Promise<PartnerProduct> {
  await ensureCsrfCookie()
  return apiFetch<PartnerProduct>(`/api/v1/partner/products/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function fetchPartnerOrderItems(signal?: AbortSignal): Promise<PartnerOrderItem[]> {
  return apiFetch<PartnerOrderItem[]>('/api/v1/partner/order-items/', { signal })
}

export async function updateFulfillment(id: number, status: FulfillmentStatus): Promise<PartnerOrderItem> {
  await ensureCsrfCookie()
  return apiFetch<PartnerOrderItem>(`/api/v1/partner/order-items/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify({ fulfillment_status: status }),
  })
}
