/**
 * Chat API：与后端 /v1/api/chat 对接
 * 支持 conversation_id（会话 ID），不传则后端复用最近会话或新建。
 * 历史以后端为唯一真相源，通过 GET /v1/api/chat/history 拉取。
 */

import { getAuthHeaders } from './auth'

const CHAT_URL = '/v1/api/chat'
const HISTORY_URL = '/v1/api/chat/history'
const CONVERSATIONS_URL = '/v1/api/chat/conversations'
const SOULS_URL = '/v1/api/souls'

/**
 * 拉取可选 Agent 人格列表（供前端筛选按钮）
 * @returns {Promise<{ souls: Array<{ id: string, name: string, description: string }> }>}
 */
export async function getSouls() {
  const res = await fetch(SOULS_URL, {
    headers: getAuthHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `请求失败: ${res.status}`)
  return data
}

/**
 * 拉取会话历史（后端为唯一真相源）
 * @param {{ user_id: string, conversation_id?: number | null }} params
 * @returns {Promise<{ conversation_id: number | null, messages: Array<{ role: string, content: string, msg_type?: string, sticker_id?: number }> }>}
 */
export async function getChatHistory(params) {
  const u = new URLSearchParams()
  u.set('user_id', params.user_id)
  if (params.conversation_id != null) u.set('conversation_id', String(params.conversation_id))
  const res = await fetch(`${HISTORY_URL}?${u}`, {
    headers: getAuthHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `请求失败: ${res.status}`)
  return data
}

/**
 * 拉取会话列表（按最近更新时间倒序）
 * @param {{ user_id: string, limit?: number }} params
 * @returns {Promise<{ conversations: Array<{ conversation_id: number, title: string, preview: string, status: string, updated_at: string | null }> }>}
 */
export async function getConversationList(params) {
  const u = new URLSearchParams()
  u.set('user_id', params.user_id)
  if (params.limit != null) u.set('limit', String(params.limit))
  const res = await fetch(`${CONVERSATIONS_URL}?${u}`, {
    headers: getAuthHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `请求失败: ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }
  return data
}

/**
 * 创建新会话（立即落库）
 * @param {{ title?: string }} payload
 */
export async function createConversation(payload = {}) {
  const res = await fetch(CONVERSATIONS_URL, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `请求失败: ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }
  return data
}

/**
 * 更新会话（重命名/置顶）
 * @param {number} conversationId
 * @param {{ title?: string, pinned?: boolean }} payload
 */
export async function updateConversation(conversationId, payload) {
  const res = await fetch(`${CONVERSATIONS_URL}/${conversationId}`, {
    method: 'PATCH',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload || {}),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `请求失败: ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }
  return data
}

/**
 * 删除会话
 * @param {number} conversationId
 */
export async function deleteConversation(conversationId) {
  const res = await fetch(`${CONVERSATIONS_URL}/${conversationId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `请求失败: ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }
  return data
}

/**
 * @param {{ user_id: string, message: string, date?: string, conversation_id?: number | null, soul_id?: string }} payload
 * @returns {Promise<{ user_id: string, conversation_id?: number, type: string, message: string, sticker_id?: number, parsed?: object, saved?: object, conflict?: object }>}
 */
export async function sendChatMessage(payload) {
  const body = {
    user_id: payload.user_id,
    message: payload.message,
    ...(payload.date && { date: payload.date }),
    ...(payload.soul_id && { soul_id: payload.soul_id }),
  }
  if (payload.conversation_id != null) {
    body.conversation_id = payload.conversation_id
  }

  const res = await fetch(CHAT_URL, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `请求失败: ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }
  return data
}
