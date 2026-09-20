import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts } from '../api/products'
import type { Product } from '../types/product'

type LoadState = 'loading' | 'ready' | 'error'

export default function CatalogPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [state, setState] = useState<LoadState>('loading')

  useEffect(() => {
    const controller = new AbortController()

    fetchProducts(controller.signal)
      .then((data) => {
        setProducts(data)
        setState('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState('error')
      })

    return () => controller.abort()
  }, [])

  if (state === 'loading') {
    return <p>Carregando catálogo…</p>
  }

  if (state === 'error') {
    return <p role="alert">Não foi possível carregar o catálogo.</p>
  }

  if (products.length === 0) {
    return <p>Nenhum produto disponível no momento.</p>
  }

  return (
    <section aria-labelledby="catalog-title">
      <h1 id="catalog-title">Catálogo</h1>
      <ul className="product-grid">
        {products.map((product) => (
          <li key={product.id} className="product-card">
            <Link to={`/produtos/${product.id}`}>
              {product.image_url && (
                <img src={product.image_url} alt="" loading="lazy" />
              )}
              <h2>{product.name}</h2>
              <p className="product-price">R$ {product.price}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
