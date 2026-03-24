const LOGIN_URL = '/v1/api/login'
const REGISTER_URL = '/v1/api/register'
const OAUTH_START_URL = '/v1/api/oauth/start'
const OAUTH_EXCHANGE_URL = '/v1/api/oauth/exchange'

export const STORAGE_USER_ID = 'betterme_chat_user_id'
export const STORAGE_TOKEN = 'betterme_auth_token'

export function getAuthToken() {
  return localStorage.getItem(STORAGE_TOKEN) || ''
}

export function getAuthUserId() {
  return localStorage.getItem(STORAGE_USER_ID) || ''
}

export function setAuthSession({ userId, token }) {
  if (userId) localStorage.setItem(STORAGE_USER_ID, userId)
  if (token) localStorage.setItem(STORAGE_TOKEN, token)
}

export function clearAuthSession() {
  localStorage.removeItem(STORAGE_USER_ID)
  localStorage.removeItem(STORAGE_TOKEN)
}

export function getAuthHeaders(extraHeaders = {}) {
  const token = getAuthToken()
  if (!token) return { ...extraHeaders }
  return {
    ...extraHeaders,
    Authorization: `Bearer ${token}`,
  }
}

export async function loginWithUserId(userId, password) {
  const res = await fetch(LOGIN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `Login failed: ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

export async function registerWithUserId(userId, password) {
  const res = await fetch(REGISTER_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `Registration failed: ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

export async function startOAuth(provider, redirectUri) {
  const res = await fetch(OAUTH_START_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, redirect_uri: redirectUri }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `Failed to start OAuth: ${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

export async function exchangeOAuthCode(provider, code, redirectUri) {
  const res = await fetch(OAUTH_EXCHANGE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, code, redirect_uri: redirectUri }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `OAuth login failed: ${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}
