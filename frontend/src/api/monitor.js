import { getAuthHeaders } from './auth'

const API_BASE = '/v1/api/monitor'

export async function listConversations(params = {}) {
  const url = new URL(`${API_BASE}/conversations`, window.location.origin)
  if (params.user_id) url.searchParams.set('user_id', params.user_id)
  if (params.limit) url.searchParams.set('limit', String(params.limit))

  const res = await fetch(url.toString(), {
    method: 'GET',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) {
    throw new Error(`listConversations failed: ${res.status}`)
  }
  return res.json()
}

export async function getConversationDetail(conversationId) {
  if (!conversationId && conversationId !== 0) {
    throw new Error('conversationId is required')
  }
  const res = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: 'GET',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) {
    throw new Error(`getConversationDetail failed: ${res.status}`)
  }
  return res.json()
}

