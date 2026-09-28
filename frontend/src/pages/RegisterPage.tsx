import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login, register, type MfaChallenge } from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'
import MfaStep from '../components/MfaStep'
import PasswordInput from '../components/PasswordInput'
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

// Mesma regra do validador de username do Django (UnicodeUsernameValidator):
// letras (inclusive acentuadas), números e @ . + - _ — sem espaços.
const USERNAME_PATTERN = /^[\p{L}\p{M}\p{N}_.@+-]+$/u

type FieldName = 'username' | 'email' | 'password'
type RegisterFieldErrors = Partial<Record<FieldName, string>>

const FIELD_NAMES: FieldName[] = ['username', 'email', 'password']

/** Separa os erros de validação do DRF por campo, para exibir cada um embaixo do input certo. */
function splitApiErrors(err: ApiError): { fields: RegisterFieldErrors; general: string | null } {
  const fields: RegisterFieldErrors = {}
  const general: string[] = []
  for (const [key, value] of Object.entries(err.fields ?? {})) {
    const messages = Array.isArray(value) ? value.filter((item) => typeof item === 'string') : []
    if (messages.length === 0) continue
    if ((FIELD_NAMES as string[]).includes(key)) {
      fields[key as FieldName] = messages.join(' ')
    } else {
      general.push(...messages)
    }
  }
  const hasAny = Object.keys(fields).length > 0 || general.length > 0
  return { fields, general: general.length > 0 ? general.join(' ') : hasAny ? null : err.message }
}

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<RegisterFieldErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null)
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const passwordChecks = getPasswordChecks(password, username)
  const usernameFormatInvalid = username.length > 0 && !USERNAME_PATTERN.test(username)
  const usernameError =
    fieldErrors.username ??
    (usernameFormatInvalid ? 'Não use espaços. Use só letras, números e @ . + - _' : undefined)

  function clearFieldError(field: FieldName) {
    setFieldErrors((current) => {
      if (!current[field]) return current
      const next = { ...current }
      delete next[field]
      return next
    })
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})
    if (usernameFormatInvalid) return
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
      if (err instanceof ApiError && err.status === 400) {
        const { fields, general } = splitApiErrors(err)
        setFieldErrors(fields)
        setError(general)
      } else {
        setError(err instanceof Error ? err.message : 'Não foi possível criar a conta.')
      }
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
          onChange={(event) => {
            setUsername(event.target.value)
            clearFieldError('username')
          }}
          maxLength={150}
          aria-invalid={usernameError ? true : undefined}
          aria-describedby={usernameError ? 'username-error' : 'username-hint'}
          required
        />
        {usernameError ? (
          <p id="username-error" className="field-error">
            {usernameError}
          </p>
        ) : (
          <p id="username-hint" className="field-hint">
            Sem espaços. Letras, números e @ . + - _
          </p>
        )}

        <label htmlFor="email">E-mail</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value)
            clearFieldError('email')
          }}
          aria-invalid={fieldErrors.email ? true : undefined}
          aria-describedby={fieldErrors.email ? 'email-error' : undefined}
          required
        />
        {fieldErrors.email && (
          <p id="email-error" className="field-error">
            {fieldErrors.email}
          </p>
        )}

        <label htmlFor="password">Senha</label>
        <PasswordInput
          id="password"
          name="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value)
            clearFieldError('password')
          }}
          aria-invalid={fieldErrors.password ? true : undefined}
          aria-describedby={fieldErrors.password ? 'password-error password-requirements' : 'password-requirements'}
          required
        />
        {fieldErrors.password && (
          <p id="password-error" className="field-error">
            {fieldErrors.password}
          </p>
        )}

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
