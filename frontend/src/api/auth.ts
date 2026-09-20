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

export async function login(data: { username: string; password: string }): Promise<User> {
  await ensureCsrfCookie()
  try {
    return await apiFetch<User>('/api/v1/auth/login/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
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

export async function logout(): Promise<void> {
  await apiFetch('/api/v1/auth/logout/', { method: 'POST' })
}
