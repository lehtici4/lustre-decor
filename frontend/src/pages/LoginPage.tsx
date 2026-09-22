import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { login, type MfaChallenge } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'
import MfaStep from '../components/MfaStep'
import type { User } from '../types/user'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const location = useLocation()
  const [error, setError] = useState<string | null>(
    (location.state as { message?: string } | null)?.message ?? null,
  )
  const [submitting, setSubmitting] = useState(false)
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null)
  const { setUser } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const result = await login({ username, password })
      if (result.kind === 'mfa') {
        setChallenge(result.challenge)
        setPassword('')
      } else {
        finish(result.user)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível entrar.')
    } finally {
      setSubmitting(false)
    }
  }

  function finish(user: User) {
    setUser(user)
    navigate('/')
  }

  if (challenge) {
    return (
      <AuthLayout
        title={challenge.stage === 'setup' ? 'Ative a verificação em dois fatores' : 'Verificação em dois fatores'}
        footer={
          <button type="button" className="link-button" onClick={() => setChallenge(null)}>
            Voltar
          </button>
        }
      >
        <MfaStep
          challenge={challenge}
          onDone={finish}
          onRestart={(message) => {
            setChallenge(null)
            setError(message)
          }}
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Entrar"
      footer={
        <>
          Ainda não tem conta? <Link to="/cadastro">Cadastre-se</Link>
        </>
      }
    >
      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Usuário</label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
        />

        <label htmlFor="password">Senha</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && <p role="alert">{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </AuthLayout>
  )
}
