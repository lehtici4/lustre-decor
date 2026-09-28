import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchCampaigns, safeColor } from '../api/campaigns'
import { fetchProducts } from '../api/products'
import type { CampaignSummary } from '../types/campaign'
import type { Product } from '../types/product'

export default function HomePage() {
  const [featured, setFeatured] = useState<Product[]>([])
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([])

  useEffect(() => {
    const controller = new AbortController()

    fetchProducts(controller.signal)
      .then((data) => setFeatured(data.slice(0, 3)))
      .catch(() => setFeatured([]))

    fetchCampaigns(controller.signal)
      .then(setCampaigns)
      .catch(() => setCampaigns([]))

    return () => controller.abort()
  }, [])

  return (
    <div className="home">
      <section className="hero">
        <p className="eyebrow">Lustre Decor</p>
        <h1>Peças com identidade para cada canto da sua casa</h1>
        <p className="hero-subtitle">
          Cerâmica, fibras naturais e metais trabalhados à mão — uma curadoria enxuta de produtos
          para casa, pensada para durar.
        </p>
        <Link to="/catalogo" className="cta-button">
          Ver catálogo
        </Link>
      </section>

      {campaigns.length > 0 && (
        <section aria-labelledby="campaigns-title" className="home-campaigns">
          <h2 id="campaigns-title">Vitrines das nossas lojas parceiras</h2>
          <ul className="campaign-grid">
            {campaigns.map((campaign) => (
              <li key={campaign.slug} className="campaign-card" style={{ borderTopColor: safeColor(campaign.accent_color) }}>
                <Link to={`/vitrines/${campaign.slug}`}>
                  <p className="campaign-store" style={{ color: safeColor(campaign.accent_color) }}>
                    {campaign.store_name}
                  </p>
                  <h3>{campaign.name}</h3>
                  {campaign.description && <p>{campaign.description}</p>}
                  <span className="campaign-link">Ver {campaign.product_count} peças →</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {featured.length > 0 && (
        <section aria-labelledby="featured-title" className="home-featured">
          <h2 id="featured-title">Destaques</h2>
          <ul className="product-grid">
            {featured.map((product) => (
              <li key={product.id} className="product-card">
                <Link to={`/produtos/${product.id}`}>
                  {product.image_url && <img src={product.image_url} alt="" loading="lazy" />}
                  <h3>{product.name}</h3>
                  <p className="product-price">R$ {product.price}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
