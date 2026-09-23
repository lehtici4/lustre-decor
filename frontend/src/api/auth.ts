import { ApiError, apiFetch, ensureCsrfCookie } from './client'
import type { User } from '../types/user'

export async function fetchCurrentUser(signal?: AbortSignal): Promise<User | null> {
  try {
    return await apiFetch<User>('/api/v1/auth/me/', { signal })
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null
    }
    throw error
  }
}

export async function register(data: { username: string; email: string; password: string }): Promise<User> {
  await ensureCsrfCookie()
  return apiFetch<User>('/api/v1/auth/register/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Desafio de MFA devolvido pelo login quando a senha está correta mas falta o
 * segundo fator (todas as contas, exceto as isentas no backend).
 * - stage "setup": primeiro acesso — traz QR code/segredo para cadastrar o app autenticador.
 * - stage "verify": conta já tem TOTP — só pede o código.
 */
export type MfaChallenge = {
  mfa_required: true
  stage: 'setup' | 'verify'
  otpauth_uri?: string
  secret?: string
  qr_code?: string
}

export type LoginResult = { kind: 'user'; user: User } | { kind: 'mfa'; challenge: MfaChallenge }

export async function login(data: { username: string; password: string }): Promise<LoginResult> {
  await ensureCsrfCookie()
  try {
    const response = await apiFetch<User | MfaChallenge>('/api/v1/auth/login/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
    if ('mfa_required' in response && response.mfa_required) {
      return { kind: 'mfa', challenge: response }
    }
    return { kind: 'user', user: response as User }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      throw new Error('Usuário ou senha inválidos.')
    }
    if (error instanceof ApiError && error.status === 429) {
      throw new Error('Muitas tentativas de login. Aguarde um momento e tente novamente.')
    }
    throw error
  }
}

/** O desafio expirou ou esgotou as tentativas: é preciso digitar a senha de novo. */
export class MfaRestartError extends Error {}

export type MfaVerifyResult = User & { backup_codes?: string[] }

export async function verifyMfa(token: string): Promise<MfaVerifyResult> {
  await ensureCsrfCookie()
  try {
    return await apiFetch<MfaVerifyResult>('/api/v1/auth/mfa/verify/', {
      method: 'POST',
      body: JSON.stringify({ token }),
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const body = (error.body ?? {}) as { restart?: boolean; attempts_left?: number }
      if (body.restart) {
        throw new MfaRestartError('Verificação expirada ou tentativas esgotadas. Entre novamente.')
      }
      const left = body.attempts_left
      throw new Error(
        left !== undefined ? `Código inválido. Tentativas restantes: ${left}.` : 'Código inválido.',
      )
    }
    if (error instanceof ApiError && error.status === 429) {
      throw new Error('Muitas tentativas. Aguarde um momento e tente novamente.')
    }
    throw error
  }
}

export async function logout(): Promise<void> {
  await apiFetch('/api/v1/auth/logout/', { method: 'POST' })
}
