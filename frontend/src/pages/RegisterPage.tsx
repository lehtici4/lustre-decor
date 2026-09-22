import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login, register, type MfaChallenge } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'
import MfaStep from '../components/MfaStep'
import type { User } from '../types/user'

type PasswordCheck = {
  label: string
  met: boolean
}

function getPasswordChecks(password: string, username: string): PasswordCheck[] {
  return [
    { label: 'Pelo menos 8 caracteres', met: password.length >= 8 },
    { label: 'Não pode ser só números', met: password.length > 0 && !/^\d+$/.test(password) },
    {
      label: 'Diferente do nome de usuário',
      met: password.length > 0 && (!username || !password.toLowerCase().includes(username.toLowerCase())),
    },
  ]
}

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null)
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const passwordChecks = getPasswordChecks(password, username)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register({ username, email, password })
      // Conta nova: o login devolve o desafio de cadastro do TOTP (MFA obrigatório).
      const result = await login({ username, password })
      if (result.kind === 'mfa') {
        setChallenge(result.challenge)
        setPassword('')
      } else {
        finish(result.user)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível criar a conta.')
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
        title="Ative a verificação em dois fatores"
        footer={
          <>
            Conta criada. A verificação em dois fatores é obrigatória para entrar — se sair agora, ela
            será pedida no próximo <Link to="/login">login</Link>.
          </>
        }
      >
        <MfaStep
          challenge={challenge}
          onDone={finish}
          onRestart={(message) => navigate('/login', { state: { message } })}
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Criar conta"
      footer={
        <>
          Já tem conta? <Link to="/login">Entrar</Link>
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

        <label htmlFor="email">E-mail</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label htmlFor="password">Senha</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-describedby="password-requirements"
          required
        />

        <ul id="password-requirements" className="password-checklist">
          {passwordChecks.map((check) => (
            <li key={check.label} className={check.met ? 'is-met' : ''}>
              <span aria-hidden="true">{check.met ? '✓' : '○'}</span> {check.label}
            </li>
          ))}
          <li>
            <span aria-hidden="true">○</span> Evite senhas muito comuns (verificado ao enviar)
          </li>
        </ul>

        {error && <p role="alert">{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Criando conta…' : 'Criar conta'}
        </button>
      </form>
    </AuthLayout>
  )
}
