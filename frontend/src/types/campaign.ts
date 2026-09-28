import type { Product } from './product'

export type CampaignSummary = {
  slug: string
  name: string
  description: string
  accent_color: string
  store_name: string
  product_count: number
}

export type CampaignDetail = CampaignSummary & { products: Product[] }

export type PartnerCampaign = {
  id: number
  store: number
  name: string
  slug: string
  description: string
  accent_color: string
  active: boolean
  starts_at: string | null
  ends_at: string | null
  products: number[]
}
