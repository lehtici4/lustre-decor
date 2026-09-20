import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export default function AuthLayout({
  title,
  children,
  footer,
}: {
  title: string
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-card-brand">
          Lustre Decor
        </Link>
        <h1 className="auth-card-title">{title}</h1>
        {children}
        <p className="auth-card-footer">{footer}</p>
      </div>
    </div>
  )
}
