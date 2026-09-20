import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App'
import RequireAuth from './components/RequireAuth'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import CartPage from './pages/CartPage'
import CatalogPage from './pages/CatalogPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import MyOrdersPage from './pages/MyOrdersPage'
import OrderDetailPage from './pages/OrderDetailPage'
import ProductDetailPage from './pages/ProductDetailPage'
import RegisterPage from './pages/RegisterPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <Routes>
            <Route path="/" element={<App />}>
              <Route index element={<HomePage />} />
              <Route path="catalogo" element={<CatalogPage />} />
              <Route path="produtos/:id" element={<ProductDetailPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="cadastro" element={<RegisterPage />} />
              <Route element={<RequireAuth />}>
                <Route path="carrinho" element={<CartPage />} />
                <Route path="pedidos" element={<MyOrdersPage />} />
                <Route path="pedidos/:id" element={<OrderDetailPage />} />
              </Route>
            </Route>
          </Routes>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
