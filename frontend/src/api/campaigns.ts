import { ApiError, apiFetch, ensureCsrfCookie } from './client'
import type { CampaignDetail, CampaignSummary, PartnerCampaign } from '../types/campaign'

export function fetchCampaigns(signal?: AbortSignal): Promise<CampaignSummary[]> {
  return apiFetch<CampaignSummary[]>('/api/v1/campaigns/', { signal })
}

export async function fetchCampaign(slug: string, signal?: AbortSignal): Promise<CampaignDetail> {
  try {
    return await apiFetch<CampaignDetail>(`/api/v1/campaigns/${encodeURIComponent(slug)}/`, { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) throw new Error('Vitrine não encontrada ou encerrada.')
    throw error
  }
}

export function fetchPartnerCampaigns(signal?: AbortSignal): Promise<PartnerCampaign[]> {
  return apiFetch<PartnerCampaign[]>('/api/v1/partner/campaigns/', { signal })
}

export async function createPartnerCampaign(
  data: Pick<PartnerCampaign, 'store' | 'name' | 'description' | 'accent_color' | 'products'>,
): Promise<PartnerCampaign> {
  await ensureCsrfCookie()
  return apiFetch<PartnerCampaign>('/api/v1/partner/campaigns/', { method: 'POST', body: JSON.stringify(data) })
}

export async function updatePartnerCampaign(
  id: number,
  data: Partial<Pick<PartnerCampaign, 'name' | 'description' | 'accent_color' | 'active' | 'products'>>,
): Promise<PartnerCampaign> {
  await ensureCsrfCookie()
  return apiFetch<PartnerCampaign>(`/api/v1/partner/campaigns/${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

/** Só aceita #RRGGBB (o backend valida igual) — valor vai para style inline. */
export function safeColor(color: string): string {
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#795b3d'
}
