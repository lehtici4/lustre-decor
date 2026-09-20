import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchProduct } from '../api/products'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import type { Product } from '../types/product'

type LoadState = 'loading' | 'ready' | 'not-found' | 'error'

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [product, setProduct] = useState<Product | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const { user } = useAuth()
  const { addItem } = useCart()
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) return

    const controller = new AbortController()
    setState('loading')

    fetchProduct(id, controller.signal)
      .then((data) => {
        setProduct(data)
        setState('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState(error instanceof Error && error.message === 'Produto não encontrado.' ? 'not-found' : 'error')
      })

    return () => controller.abort()
  }, [id])

  async function handleAddToCart() {
    if (!product) return

    if (!user) {
      navigate('/login')
      return
    }

    setAddError(null)
    setAdding(true)
    try {
      await addItem(product.id, 1)
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Não foi possível adicionar ao carrinho.')
    } finally {
      setAdding(false)
    }
  }

  if (state === 'loading') {
    return <p>Carregando produto…</p>
  }

  if (state === 'not-found') {
    return (
      <p role="alert">
        Produto não encontrado. <Link to="/catalogo">Voltar ao catálogo</Link>
      </p>
    )
  }

  if (state === 'error' || !product) {
    return <p role="alert">Não foi possível carregar o produto.</p>
  }

  return (
    <article aria-labelledby="product-title">
      <p>
        <Link to="/catalogo">← Voltar ao catálogo</Link>
      </p>
      {product.image_url && <img src={product.image_url} alt="" className="product-detail-image" />}
      <h1 id="product-title">{product.name}</h1>
      <p className="product-price">R$ {product.price}</p>
      <p>{product.description}</p>
      {addError && <p role="alert">{addError}</p>}
      <button type="button" onClick={handleAddToCart} disabled={adding}>
        {adding ? 'Adicionando…' : 'Adicionar ao carrinho'}
      </button>
    </article>
  )
}
