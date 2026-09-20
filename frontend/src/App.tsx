import { Link, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { useCart } from './context/CartContext'
import './styles.css'

export default function App() {
  const { user, loading, logout } = useAuth()
  const { itemCount } = useCart()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          Lustre Decor
        </Link>
        <nav className="app-nav">
          <Link to="/catalogo">Catálogo</Link>
          {user && <Link to="/pedidos">Meus pedidos</Link>}
        </nav>
        {!loading && (
          <div className="auth-nav">
            {user ? (
              <>
                <Link to="/carrinho">Carrinho ({itemCount})</Link>
                <span>Olá, {user.username}</span>
                <button type="button" onClick={handleLogout}>
                  Sair
                </button>
              </>
            ) : (
              <>
                <Link to="/login">Entrar</Link>
                <Link to="/cadastro">Cadastrar</Link>
              </>
            )}
          </div>
        )}
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
