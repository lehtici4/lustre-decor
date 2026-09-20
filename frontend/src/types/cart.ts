export type CartItem = {
  id: number
  product_id: number
  product_name: string
  unit_price: string
  quantity: number
  subtotal: string
}

export type Cart = {
  id: number
  items: CartItem[]
  total: string
}
