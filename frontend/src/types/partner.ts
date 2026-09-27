export type PartnerStore = {
  id: number
  name: string
}

export type PartnerProduct = {
  id: number
  store: number
  store_name: string
  name: string
  description: string
  price: string
  active: boolean
  image_url: string
  updated_at: string
}

export type PartnerProductInput = {
  store: number
  name: string
  description: string
  price: string
  image_url?: string
}

export type FulfillmentStatus = 'pending' | 'shipped'

export type PartnerOrderItem = {
  id: number
  order_id: number
  order_created_at: string
  order_status: string
  store_name: string
  product_name: string
  unit_price: string
  quantity: number
  fulfillment_status: FulfillmentStatus
}
