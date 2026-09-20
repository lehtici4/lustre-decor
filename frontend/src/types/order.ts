export type OrderItem = {
  id: number
  product_name: string
  unit_price: string
  quantity: number
}

export type Order = {
  id: number
  status: string
  total: string
  created_at: string
  items: OrderItem[]
}
