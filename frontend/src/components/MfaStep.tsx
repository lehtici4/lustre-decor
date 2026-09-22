import { useState, type FormEvent } from 'react'
import { MfaRestartError, verifyMfa, type MfaChallenge } from '../api/auth'
import type { User } from '../types/user'

type Props = {
  challenge: MfaChallenge
  /** Chamado com o usuário já autenticado (sessão criada após o segundo fator). */
  onDone: (user: User) => void
  /** Desafio expirado/esgotado: volta para a tela de usuário e senha. */
  onRestart: (message: string) => void
}

export default function MfaStep({ challenge, onDone, onRestart }: Props) {
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [verified, setVerified] = useState<{ user: User; codes: string[] } | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { backup_codes: codes, ...user } = await verifyMfa(token)
      if (codes && codes.length > 0) {
        // Primeiro cadastro: mostra os códigos de backup uma única vez antes de seguir.
        setVerified({ user, codes })
      } else {
        onDone(user)
      }
    } catch (err) {
      if (err instanceof MfaRestartError) {
        onRestart(err.message)
        return
      }
      setError(err instanceof Error ? err.message : 'Não foi possível verificar o código.')
      setToken('')
    } finally {
      setSubmitting(false)
    }
  }

  if (verified) {
    return (
      <div className="mfa-step">
        <p>
          Autenticação em dois fatores ativada. Guarde estes <strong>códigos de backup</strong> em local
          seguro: cada um pode ser usado <strong>uma única vez</strong> se você perder acesso ao app
          autenticador. Eles não serão mostrados novamente.
        </p>
        <ul className="mfa-backup-codes">
          {verified.codes.map((code) => (
            <li key={code}>
              <code>{code}</code>
            </li>
          ))}
        </ul>
        <button type="button" className="mfa-primary" onClick={() => onDone(verified.user)}>
          Já guardei os códigos — continuar
        </button>
      </div>
    )
  }

  return (
    <div className="mfa-step">
      {challenge.stage === 'setup' ? (
        <>
          <p>
            Para proteger sua conta, o acesso exige um segundo fator. Escaneie o QR code com um app
            autenticador (Google Authenticator, Microsoft Authenticator, Aegis…) e digite o código de 6
            dígitos gerado.
          </p>
          {challenge.qr_code && (
            <img className="mfa-qr" src={challenge.qr_code} alt="QR code para configurar o app autenticador" />
          )}
          {challenge.secret && (
            <details className="mfa-secret">
              <summary>Não consegue escanear? Digite a chave manualmente</summary>
              <code>{challenge.secret.match(/.{1,4}/g)?.join(' ')}</code>
            </details>
          )}
        </>
      ) : (
        <p>Digite o código de 6 dígitos do seu app autenticador. Se perdeu o acesso ao app, use um dos seus códigos de backup.</p>
      )}

      <form onSubmit={handleSubmit}>
        <label htmlFor="mfa-token">Código de verificação</label>
        <input
          id="mfa-token"
          name="token"
          inputMode={challenge.stage === 'setup' ? 'numeric' : 'text'}
          autoComplete="one-time-code"
          autoFocus
          maxLength={16}
          value={token}
          onChange={(event) => setToken(event.target.value)}
          required
        />

        {error && <p role="alert">{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Verificando…' : challenge.stage === 'setup' ? 'Ativar e entrar' : 'Verificar'}
        </button>
      </form>
    </div>
  )
}
