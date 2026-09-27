import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchCampaign, safeColor } from '../api/campaigns'
import type { CampaignDetail } from '../types/campaign'

export default function CampaignPage() {
  const { slug = '' } = useParams()
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchCampaign(slug, controller.signal)
      .then(setCampaign)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Não foi possível carregar a vitrine.')
      })
    return () => controller.abort()
  }, [slug])

  if (error) return <p role="alert">{error}</p>
  if (!campaign) return <p>Carregando vitrine…</p>

  const accent = safeColor(campaign.accent_color)

  return (
    <section aria-labelledby="campaign-title">
      <header className="campaign-hero" style={{ borderColor: accent }}>
        <p className="eyebrow" style={{ color: accent }}>
          Vitrine · {campaign.store_name}
        </p>
        <h1 id="campaign-title">{campaign.name}</h1>
        {campaign.description && <p className="hero-subtitle">{campaign.description}</p>}
      </header>
      <ul className="product-grid">
        {campaign.products.map((product) => (
          <li key={product.id} className="product-card">
            <Link to={`/produtos/${product.id}`}>
              {product.image_url && <img src={product.image_url} alt="" loading="lazy" />}
              <h2>{product.name}</h2>
              <p className="product-price">R$ {product.price}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
