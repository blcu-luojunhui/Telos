<template>
  <div class="workspace-page">
    <div class="workspace-shell">
      <aside class="workspace-sidebar" :style="{ width: `${sidebarWidth}px` }">
        <div class="sidebar-brand">
          <div class="logo-icon">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="brand-text">
            <p class="brand-title">Personal Work Agent</p>
            <p class="brand-status"><span class="online-dot"></span>在线</p>
          </div>
        </div>

        <button
          type="button"
          class="new-session-btn sidebar-new-btn"
          @click="startNewSession"
          title="创建新会话"
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>新建会话</span>
        </button>

        <div class="sidebar-group sessions-scroll">
          <p class="sidebar-label">RECENT</p>
          <div v-if="sessionLoading" class="sidebar-empty">加载会话中...</div>
          <template v-else>
            <div
              v-for="item in sessionList"
              :key="item.conversation_id"
              class="sidebar-item"
              :class="{ active: sessionId === item.conversation_id }"
              @click="openConversation(item.conversation_id)"
              :title="item.preview || item.title"
              role="button"
              tabindex="0"
              @keydown.enter.prevent="openConversation(item.conversation_id)"
            >
              <span class="session-row">
                <span class="session-title-wrap">
                  <span v-if="item.pinned" class="session-pin">📌</span>
                  <span class="session-title">{{ item.title }}</span>
                </span>
                <span class="session-actions">
                  <button class="session-action" type="button" title="重命名" @click.stop="renameConversation(item)">✏️</button>
                  <button class="session-action" type="button" :title="item.pinned ? '取消置顶' : '置顶'" @click.stop="togglePinConversation(item)">
                    {{ item.pinned ? '📍' : '📌' }}
                  </button>
                  <button class="session-action danger" type="button" title="删除会话" @click.stop="removeConversation(item)">🗑</button>
                </span>
              </span>
              <span v-if="item.updated_at" class="session-time">{{ formatTime(item.updated_at) }}</span>
            </div>
            <div v-if="sessionList.length === 0" class="sidebar-empty">暂无会话，开始新对话吧</div>
          </template>
        </div>

        <div class="sidebar-spacer"></div>

        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="sidebar-user-avatar">{{ (userId || 'U').slice(0, 1).toUpperCase() }}</div>
            <div class="sidebar-user-meta">
              <p class="sidebar-user-name">{{ userId }}</p>
              <p class="sidebar-user-level">已登录</p>
            </div>
            <button @click="logout" class="logout-btn" title="退出登录">退出</button>
          </div>
        </div>
      </aside>

      <div
        class="sidebar-divider"
        title="拖拽调整会话栏宽度"
        @mousedown="startResize"
      ></div>

      <section class="workspace-main">
        <header class="chat-header">
          <div class="header-glow" aria-hidden="true"></div>
          <div class="chat-title-wrap">
            <p class="chat-title">{{ chatTitle }}</p>
            <button class="title-edit-btn" type="button" @click="editChatTitle" title="修改标题">编辑</button>
          </div>
          <div class="soul-bar">
            <span class="soul-label">人格</span>
            <div class="soul-btns">
              <button
                v-for="s in souls"
                :key="s.id ?? s.slug"
                type="button"
                class="soul-btn"
                :class="{ active: selectedSoulId === (s.slug ?? s.id) }"
                :title="s.description"
                @click="selectedSoulId = (s.slug ?? s.id)"
              >
                {{ s.name }}
              </button>
            </div>
          </div>
        </header>

        <main class="chat-main">
          <div class="messages-container" ref="messagesRef">
            <div v-if="messages.length === 0" class="empty-state">
              <div class="empty-icon">💬</div>
              <h2 class="empty-title">你好，{{ userId }}</h2>
              <p class="empty-desc">
                在这里和 BetterMe 聊天、做计划、记录生活。
              </p>
            </div>

            <transition-group name="msg-fade">
              <div
                v-for="row in displayedMessages"
                :key="row.key"
                class="msg-wrapper"
                :class="[row.msg.role, { 'msg-continuation': row.part === 'text' }]"
              >
                <div class="msg-avatar" v-if="row.msg.role === 'bot' && row.part !== 'text'">
                  <AnimatedShrimp :action="parseBotMessage(row.msg.text).action" />
                </div>
                <div class="msg-avatar msg-avatar-placeholder" v-else-if="row.msg.role === 'bot' && row.part === 'text'"></div>

                <div class="msg-content">
                  <div class="msg-bubble" :class="{ error: row.msg.isError, 'msg-bubble--sticker': row.part === 'sticker' }">
                    <img
                      v-if="row.part === 'sticker' && stickerUrl(row.msg.stickerId)"
                      :src="stickerUrl(row.msg.stickerId)"
                      :alt="`表情${row.msg.stickerId}`"
                      class="msg-sticker"
                    />
                    <div
                      v-if="row.part !== 'sticker' && row.msg.role === 'bot' && row.msg.planPreview"
                      class="plan-preview"
                    >
                      <div class="plan-preview-head">
                        <p class="plan-title">已记录：目标 【{{ row.msg.planPreview.title || '训练计划' }}】</p>
                        <p v-if="row.msg.planId != null" class="plan-meta">计划 ID：{{ row.msg.planId }}</p>
                        <p class="plan-meta">
                          周期：{{ row.msg.planPreview.start_date || '-' }} 至 {{ row.msg.planPreview.end_date || '-' }}
                        </p>
                        <p class="plan-meta">
                          共 {{ planTotalDays(row.msg.planPreview) }} 天、{{ planTotalSessions(row.msg.planPreview) }} 次训练安排
                        </p>
                      </div>
                      <div class="plan-table-wrap">
                        <table class="plan-table">
                          <thead>
                            <tr>
                              <th>日期</th>
                              <th>周次</th>
                              <th>类型</th>
                              <th>安排</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="item in planRows(row.msg.planPreview)" :key="item.key">
                              <td>{{ item.date }}</td>
                              <td>{{ item.week }}</td>
                              <td>{{ item.type }}</td>
                              <td>{{ item.summary }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <p v-if="planRemainingDays(row.msg.planPreview) > 0" class="plan-tail">
                        … 后续 {{ planRemainingDays(row.msg.planPreview) }} 天详见完整计划。
                      </p>
                      <p v-if="row.msg.planNeedsConfirm" class="plan-tail">回复「确认」保存此计划，回复「取消」放弃。</p>
                    </div>
                    <p v-else-if="row.part !== 'sticker'" class="msg-text">{{ row.msg.role === 'bot' ? stripParentheses(parseBotMessage(row.msg.text).body) : row.msg.text }}</p>
                  </div>
                </div>

                <div class="msg-avatar user-avatar" v-if="row.msg.role === 'user'">
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M12 11C14.2091 11 16 9.20914 16 7C16 4.79086 14.2091 3 12 3C9.79086 3 8 4.79086 8 7C8 9.20914 9.79086 11 12 11Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </transition-group>

            <div class="msg-wrapper bot" v-if="loading">
              <div class="msg-avatar">
                <AnimatedShrimp action="idle" />
              </div>
              <div class="msg-content">
                <div class="msg-bubble typing">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>

          <div class="input-container">
            <div class="input-wrapper">
              <textarea
                v-model="inputText"
                class="chat-input"
                placeholder="请输入你想聊的内容，Shift+Enter 换行"
                autocomplete="off"
                :disabled="loading"
                @compositionstart="handleCompositionStart"
                @compositionend="handleCompositionEnd"
                @keydown.enter.exact.prevent="handleEnter"
              ></textarea>
              <button
                type="button"
                class="send-btn"
                :class="{ active: inputText.length > 0 }"
                :disabled="loading || !inputText"
                @click="send"
                aria-label="发送"
              >
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        </main>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  sendChatMessage,
  getChatHistory,
  getSouls,
  getConversationList,
  createConversation,
  updateConversation,
  deleteConversation,
} from '../api/chat'
import { clearAuthSession, getAuthToken } from '../api/auth'
import AnimatedShrimp from '../components/AnimatedShrimp.vue'

/** 从 bot 消息中解析 (钳子xxx) 动作与正文 */
const ACTION_REG = /^\(钳子(.+?)\)\s*([\s\S]*)$/
const ACTION_MAP = {
  '懒洋洋晃了晃': 'sway',
  '不耐烦地敲了敲': 'tap',
  '顿了一下': 'pause',
  '戳了戳屏幕': 'poke',
}
function parseBotMessage(text) {
  if (!text || typeof text !== 'string') return { action: 'idle', actionLabel: '', body: text || '' }
  const m = text.trim().match(ACTION_REG)
  if (!m) return { action: 'idle', actionLabel: '', body: text }
  const [, actionLabel, body] = m
  const action = ACTION_MAP[actionLabel.trim()] || 'idle'
  return { action, actionLabel: `(钳子${actionLabel.trim()})`, body: body.trim() }
}

/** 移除文本中所有括号及其内容，包括 () 和 （） */
function stripParentheses(text) {
  if (!text || typeof text !== 'string') return text || ''
  return text
    .replace(/[（(][^）)]*[）)]/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

const STICKER_FILES = [
  'lobster-sticker-01-chayao.png',
  'lobster-sticker-02-jiangzhu.png',
  'lobster-sticker-03-fadou.png',
  'lobster-sticker-04-manmanfangxia.png',
  'lobster-sticker-05-lizheng.png',
  'lobster-sticker-06-fanbaiyan.png',
  'lobster-sticker-07-qidezhuanquan.png',
  'lobster-sticker-08-qiaonao.png',
  'lobster-sticker-09-tandao.png',
  'lobster-sticker-10-bige-ye.png',
  'lobster-sticker-11-bengdi.png',
  'lobster-sticker-12-dajiepai.png',
  'lobster-sticker-13-shuaishuai.png',
  'lobster-sticker-14-cahan.png',
  'lobster-sticker-15-meiyan.png',
  'lobster-sticker-16-dunfang.png',
  'lobster-sticker-17-toutoumiaoni.png',
  'lobster-sticker-18-jiaqian.png',
  'lobster-sticker-19-houkongfan.png',
  'lobster-sticker-20-tangping.png',
  'lobster-sticker-21-bixin.png',
  'lobster-sticker-22-wulian.png',
  'lobster-sticker-23-zhengfa.png',
  'lobster-sticker-24-pahuilai.png',
  'lobster-sticker-25-guangji.png'
]
function stickerUrl(stickerId) {
  if (!stickerId || stickerId < 1 || stickerId > 25) return ''
  return `/assets/stickers/${STICKER_FILES[stickerId - 1]}`
}

const STORAGE_USER_ID = 'betterme_chat_user_id'

const router = useRouter()
const userId = ref('')
const sessionId = ref(null) // 当前会话 ID（对应后端 conversation_id），null 表示下次发消息时由后端新建或复用
const inputText = ref('')
const loading = ref(false)
const messages = ref([])
const messagesRef = ref(null)
const isComposing = ref(false)
const souls = ref([])
const selectedSoulId = ref('rude')
const sessionList = ref([])
const sessionLoading = ref(false)
const chatTitle = ref(localStorage.getItem('betterme_chat_title') || '-personal-work-agent')
const sidebarWidth = ref(parseInt(localStorage.getItem('betterme_sidebar_width') || '290', 10))
const DEFAULT_SOULS = [
  { slug: 'rude', name: '暴躁龙虾', description: '有脾气、爱吐槽，嘴硬心软' },
  { slug: 'gentle', name: '温柔小助手', description: '耐心体贴，语气温和' },
  { slug: 'professional', name: '专业简洁', description: '简洁专业，直接给结论' },
  { slug: 'funny', name: '幽默搞怪', description: '轻松搞笑，爱接梗' },
]

function applySouls(inputSouls) {
  const list = Array.isArray(inputSouls) && inputSouls.length > 0 ? inputSouls : DEFAULT_SOULS
  souls.value = list
  const storedSoul = localStorage.getItem('betterme_soul_id')
  const hasStored = storedSoul && list.some((s) => (s.slug || s.id) === storedSoul)
  if (hasStored) {
    selectedSoulId.value = storedSoul
    return
  }
  selectedSoulId.value = (list[0] && (list[0].slug || list[0].id)) || 'rude'
}

/** 有表情且有正文时拆成两条展示：先表情，再文字 */
const displayedMessages = computed(() => {
  const list = []
  messages.value.forEach((msg, i) => {
    if (msg.role === 'bot' && msg.stickerId) {
      const body = stripParentheses(parseBotMessage(msg.text).body)
      if (body) {
        list.push({ msg, part: 'sticker', key: `bot-${i}-sticker` })
        list.push({ msg, part: 'text', key: `bot-${i}-text` })
      } else {
        list.push({ msg, part: 'sticker', key: `bot-${i}` })
      }
    } else {
      list.push({ msg, part: null, key: `${msg.role}-${i}` })
    }
  })
  return list
})

/** 把后端历史条目标准格式转为前端消息格式（后端 role 为 assistant，前端展示用 bot） */
function historyItemToMessage(item) {
  return {
    role: item.role === 'assistant' ? 'bot' : item.role,
    text: item.content ?? '',
    isError: item.msg_type === 'error',
    stickerId: item.sticker_id != null ? item.sticker_id : undefined,
    planPreview: item.extra && item.extra.plan_preview ? item.extra.plan_preview : undefined,
    planNeedsConfirm: item.extra ? Boolean(item.extra.plan_requires_confirm) : false,
    planId: item.extra && item.extra.plan_id != null ? item.extra.plan_id : undefined,
    soulId: item.soul_id ?? undefined,
    soul: item.soul ?? undefined,
  }
}

const PLAN_PREVIEW_DAYS = 14

function planTotalDays(preview) {
  return Array.isArray(preview && preview.days) ? preview.days.length : 0
}

function planTotalSessions(preview) {
  const days = Array.isArray(preview && preview.days) ? preview.days : []
  return days.reduce((sum, d) => sum + (Array.isArray(d.sessions) ? d.sessions.length : 0), 0)
}

function slotTypeCn(type) {
  const map = {
    rest: '休息',
    easy: '轻松跑',
    long_run: '长距离',
    quality: '节奏/间歇',
    cardio: '有氧',
    strength: '力量',
    long_walk: '长时间步行',
  }
  return map[type] || type || '训练'
}

function planRows(preview) {
  const days = Array.isArray(preview && preview.days) ? preview.days.slice(0, PLAN_PREVIEW_DAYS) : []
  const rows = []
  days.forEach((d, idx) => {
    const sessions = Array.isArray(d.sessions) && d.sessions.length > 0 ? d.sessions : [{ slot_type: 'rest', summary: '主动休息' }]
    sessions.forEach((s, j) => {
      rows.push({
        key: `${d.date || 'date'}-${idx}-${j}`,
        date: d.date || '-',
        week: d.week_index ? `第${d.week_index}周` : '-',
        type: slotTypeCn(s.slot_type),
        summary: s.summary || '-',
      })
    })
  })
  return rows
}

function planRemainingDays(preview) {
  const total = planTotalDays(preview)
  return total > PLAN_PREVIEW_DAYS ? (total - PLAN_PREVIEW_DAYS) : 0
}

onMounted(async () => {
  userId.value = localStorage.getItem(STORAGE_USER_ID) || ''
  if (!userId.value || !getAuthToken()) {
    clearAuthSession()
    router.push('/')
    return
  }
  const key = `betterme_chat_session_${userId.value}`
  const stored = localStorage.getItem(key)
  let hintConvId = null
  if (stored !== null && stored !== '') {
    const n = parseInt(stored, 10)
    if (!Number.isNaN(n)) hintConvId = n
  }
  applySouls([])
  try {
    const [historyRes, soulsRes, convRes] = await Promise.all([
      getChatHistory({ user_id: userId.value, conversation_id: hintConvId }),
      getSouls().catch(() => ({ souls: [] })),
      getConversationList({ user_id: userId.value, limit: 50 }).catch(() => ({ conversations: [] })),
    ])
    const { conversation_id, messages: list } = historyRes
    applySouls(soulsRes.souls)
    sessionId.value = conversation_id ?? null
    if (sessionId.value != null) {
      localStorage.setItem(key, String(sessionId.value))
    } else {
      localStorage.removeItem(key)
    }
    messages.value = Array.isArray(list) ? list.map(historyItemToMessage) : []
    sessionList.value = Array.isArray(convRes.conversations) ? convRes.conversations : []
  } catch (_e) {
    if (_e && _e.status === 401) {
      clearAuthSession()
      router.push('/')
      return
    }
    sessionId.value = null
    localStorage.removeItem(key)
    messages.value = []
    sessionList.value = []
    applySouls([])
  }
  if (Number.isNaN(sidebarWidth.value) || sidebarWidth.value < 220 || sidebarWidth.value > 460) {
    sidebarWidth.value = 290
  }
})

watch(selectedSoulId, (id) => {
  if (id) localStorage.setItem('betterme_soul_id', id)
})

function persistSessionId() {
  if (!userId.value) return
  const key = `betterme_chat_session_${userId.value}`
  if (sessionId.value != null) {
    localStorage.setItem(key, String(sessionId.value))
  } else {
    localStorage.removeItem(key)
  }
}

async function startNewSession() {
  sessionId.value = null
  messages.value = []
  persistSessionId()
  try {
    const created = await createConversation({})
    if (created && created.conversation_id != null) {
      sessionId.value = Number(created.conversation_id)
      persistSessionId()
    }
    await refreshSessionList()
  } catch (e) {
    if (e && e.status === 401) {
      clearAuthSession()
      router.push('/')
    }
  }
}

function editChatTitle() {
  const next = window.prompt('请输入新的标题', chatTitle.value || '')
  if (next === null) return
  const val = next.trim() || '-personal-work-agent'
  chatTitle.value = val.slice(0, 64)
  localStorage.setItem('betterme_chat_title', chatTitle.value)
}

async function renameConversation(item) {
  const next = window.prompt('输入新的会话名称', item.title || '')
  if (next === null) return
  try {
    await updateConversation(item.conversation_id, { title: next.trim() })
    await refreshSessionList()
  } catch (_e) {
    // ignore
  }
}

async function togglePinConversation(item) {
  try {
    await updateConversation(item.conversation_id, { pinned: !item.pinned })
    await refreshSessionList()
  } catch (_e) {
    // ignore
  }
}

async function removeConversation(item) {
  const ok = window.confirm(`确认删除会话「${item.title || item.conversation_id}」？`)
  if (!ok) return
  try {
    await deleteConversation(item.conversation_id)
    if (sessionId.value === item.conversation_id) {
      sessionId.value = null
      messages.value = []
      persistSessionId()
    }
    await refreshSessionList()
  } catch (_e) {
    // ignore
  }
}

async function refreshSessionList() {
  if (!userId.value) return
  sessionLoading.value = true
  try {
    const res = await getConversationList({ user_id: userId.value, limit: 50 })
    sessionList.value = Array.isArray(res.conversations) ? res.conversations : []
  } catch (_e) {
    sessionList.value = []
  } finally {
    sessionLoading.value = false
  }
}

async function openConversation(conversationId) {
  if (!conversationId || loading.value) return
  try {
    const historyRes = await getChatHistory({
      user_id: userId.value,
      conversation_id: conversationId,
    })
    sessionId.value = historyRes.conversation_id ?? null
    persistSessionId()
    messages.value = Array.isArray(historyRes.messages)
      ? historyRes.messages.map(historyItemToMessage)
      : []
    scrollToBottom()
  } catch (e) {
    if (e && e.status === 401) {
      clearAuthSession()
      router.push('/')
    }
  }
}

function formatTime(isoText) {
  if (!isoText) return ''
  const dt = new Date(isoText)
  if (Number.isNaN(dt.getTime())) return ''
  const now = new Date()
  const sameDay = dt.toDateString() === now.toDateString()
  if (sameDay) return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return dt.toLocaleDateString([], { month: 'numeric', day: 'numeric' })
}

function startResize(e) {
  e.preventDefault()
  const onMove = (ev) => {
    const w = Math.min(460, Math.max(220, ev.clientX))
    sidebarWidth.value = w
  }
  const onUp = () => {
    localStorage.setItem('betterme_sidebar_width', String(sidebarWidth.value))
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

const logout = () => {
  if (userId.value) {
    localStorage.removeItem(`betterme_chat_session_${userId.value}`)
  }
  clearAuthSession()
  router.push('/')
}

const handleCompositionStart = () => {
  isComposing.value = true
}

const handleCompositionEnd = () => {
  isComposing.value = false
}

const handleEnter = (event) => {
  if (event.isComposing || isComposing.value) return
  if (event.shiftKey) return
  if (loading.value) return
  if (!inputText.value.trim()) return
  send()
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTo({
      top: messagesRef.value.scrollHeight,
      behavior: 'smooth'
    })
  }
}

async function send() {
  const text = inputText.value
  if (!text) return

  const uid = userId.value || 'user_001'

  messages.value.push({ role: 'user', text, isError: false })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const payload = { user_id: uid, message: text }
    if (sessionId.value != null) payload.conversation_id = sessionId.value
    if (selectedSoulId.value) payload.soul_id = selectedSoulId.value
    const data = await sendChatMessage(payload)
    if (data.conversation_id != null) {
      sessionId.value = data.conversation_id
      persistSessionId()
    }
    const reply = data.message != null ? String(data.message) : '（无回复内容）'
    messages.value.push({
      role: 'bot',
      text: reply,
      isError: data.type === 'error',
      stickerId: data.sticker_id != null ? data.sticker_id : undefined,
      planPreview: data.extra && data.extra.plan_preview ? data.extra.plan_preview : undefined,
      planNeedsConfirm: data.extra ? Boolean(data.extra.plan_requires_confirm) : false,
      planId: data.extra && data.extra.plan_id != null ? data.extra.plan_id : undefined,
    })
  } catch (e) {
    if (e && e.status === 401) {
      clearAuthSession()
      router.push('/')
      return
    }
    messages.value.push({
      role: 'bot',
      text: '网络错误: ' + (e.message || String(e)),
      isError: true,
    })
  } finally {
    loading.value = false
    refreshSessionList()
    scrollToBottom()
  }
}
</script>

<style scoped>
.workspace-page {
  --od-bg-0: #1e2127;
  --od-bg-1: #23272e;
  --od-bg-2: #2c313a;
  --od-panel: rgba(34, 39, 46, 0.88);
  --od-panel-strong: rgba(36, 42, 50, 0.96);
  --od-border: rgba(92, 103, 122, 0.35);
  --od-text: #d7dae0;
  --od-text-soft: #abb2bf;
  --od-accent: #61afef;
  --od-accent-soft: rgba(97, 175, 239, 0.2);
  min-height: 100vh;
  min-height: 100dvh;
  height: 100vh;
  height: 100dvh;
  padding: 0;
  background: radial-gradient(1300px 700px at 15% -30%, #2b3038 0%, #1e2127 40%, #171a20 100%);
}

.workspace-shell {
  width: 100%;
  height: 100%;
  margin: 0;
  background: var(--od-bg-0);
  border: none;
  border-radius: 0;
  overflow: hidden;
  display: flex;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.workspace-sidebar {
  border-right: 1px solid var(--od-border);
  background: linear-gradient(180deg, var(--od-panel-strong) 0%, var(--od-panel) 100%);
  padding: 1.1rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  transition: width 80ms linear;
}

.sidebar-divider {
  width: 8px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  z-index: 3;
}

.sidebar-divider::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  left: 3px;
  width: 2px;
  background: linear-gradient(180deg, rgba(97, 175, 239, 0.18), rgba(97, 175, 239, 0.05));
  opacity: 0.35;
  transition: opacity 0.2s ease;
}

.sidebar-divider:hover::before {
  opacity: 0.9;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.45rem 0.55rem;
}

.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b5c5ee;
  background: rgba(73, 98, 160, 0.24);
}

.logo-icon svg {
  width: 18px;
  height: 18px;
}

.brand-title {
  margin: 0;
  color: var(--od-text);
  font-weight: 650;
  font-size: 0.95rem;
}

.brand-status {
  margin: 0.2rem 0 0;
  color: #7adfa8;
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.online-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2ed287;
}

.sidebar-new-btn {
  width: 100%;
  justify-content: center;
  background: linear-gradient(180deg, rgba(37, 50, 86, 0.9), rgba(26, 37, 67, 0.95));
  color: #e8efff;
  border: 1px solid rgba(142, 165, 213, 0.35);
  border-radius: 10px;
  padding: 0.62rem 0.75rem;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.sidebar-new-btn:hover {
  border-color: rgba(163, 188, 245, 0.68);
  background: linear-gradient(180deg, rgba(44, 58, 96, 0.95), rgba(31, 44, 75, 0.98));
}

.sidebar-new-btn svg {
  width: 15px;
  height: 15px;
}

.sidebar-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.sidebar-label {
  margin: 0.45rem 0 0.2rem;
  padding: 0 0.45rem;
  color: var(--od-text-soft);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
}

.sidebar-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  color: var(--od-text);
  border-radius: 9px;
  padding: 0.57rem 0.62rem;
  font-size: 0.86rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sidebar-item:hover {
  background: var(--od-accent-soft);
}

.sidebar-item.active {
  background: var(--od-accent-soft);
  border-color: rgba(97, 175, 239, 0.55);
  color: #f4f8ff;
}

.sidebar-spacer {
  flex: 1;
}

.sidebar-footer {
  border-top: 1px solid rgba(139, 162, 211, 0.2);
  padding-top: 0.8rem;
}

.sidebar-user {
  margin-top: 0.55rem;
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.sidebar-user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #5f7cc7, #3d5a9f);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 700;
}

.sidebar-user-meta {
  flex: 1;
  min-width: 0;
}

.sidebar-user-name,
.sidebar-user-level {
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-user-name {
  color: #e8efff;
  font-size: 0.82rem;
  font-weight: 600;
}

.sidebar-user-level {
  color: #8fa2cd;
  font-size: 0.74rem;
  margin-top: 0.1rem;
}

.logout-btn {
  border: 1px solid rgba(136, 159, 209, 0.35);
  background: rgba(57, 74, 122, 0.35);
  color: #c8d5f6;
  border-radius: 7px;
  font-size: 0.75rem;
  padding: 0.32rem 0.48rem;
  cursor: pointer;
}

.logout-btn:hover {
  border-color: rgba(239, 138, 138, 0.7);
  color: #ffc1c1;
}

.workspace-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(30, 33, 39, 0.96), rgba(24, 27, 33, 0.98));
}

.chat-header {
  min-height: 64px;
  padding: 0.7rem 1.1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--od-border);
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01));
  backdrop-filter: blur(12px) saturate(120%);
}

.header-glow {
  position: absolute;
  top: -80px;
  left: -140px;
  width: 360px;
  height: 220px;
  pointer-events: none;
  background: radial-gradient(circle at center, rgba(97, 175, 239, 0.32), rgba(97, 175, 239, 0) 70%);
  filter: blur(16px);
  animation: glow-move 8s ease-in-out infinite alternate;
}

@keyframes glow-move {
  from { transform: translateX(0px) translateY(0px); opacity: 0.75; }
  to { transform: translateX(120px) translateY(10px); opacity: 0.35; }
}

.chat-title {
  margin: 0;
  color: #e4e8ef;
  font-size: 0.97rem;
  font-weight: 600;
}

.chat-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title-edit-btn {
  border: 1px solid rgba(109, 121, 143, 0.35);
  background: rgba(255, 255, 255, 0.04);
  color: var(--od-text-soft);
  border-radius: 8px;
  font-size: 0.72rem;
  padding: 0.2rem 0.45rem;
  cursor: pointer;
}

.title-edit-btn:hover {
  border-color: rgba(97, 175, 239, 0.55);
  color: var(--od-text);
  background: rgba(97, 175, 239, 0.12);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  scroll-behavior: smooth;
}

.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: rgba(120, 132, 153, 0.45);
  border-radius: 10px;
}

.empty-state {
  margin: auto;
  text-align: center;
  color: var(--od-text-soft);
}

.empty-icon {
  font-size: 2.2rem;
  margin-bottom: 0.5rem;
}

.empty-title {
  margin: 0;
  color: var(--od-text);
  font-size: 1.2rem;
}

.empty-desc {
  margin: 0.6rem 0 0;
  font-size: 0.92rem;
}

.msg-wrapper {
  display: flex;
  gap: 0.7rem;
  align-items: flex-end;
  max-width: 76%;
  animation: msg-appear 260ms cubic-bezier(0.22, 1, 0.36, 1);
}

.msg-wrapper.user {
  align-self: flex-end;
}

.msg-wrapper.bot {
  align-self: flex-start;
}

.msg-avatar {
  width: 33px;
  height: 33px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bot .msg-avatar {
  background: rgba(75, 103, 169, 0.3);
}

.user-avatar {
  background: rgba(70, 85, 123, 0.65);
  color: #f4f8ff;
}

.msg-avatar svg {
  width: 18px;
  height: 18px;
}

.msg-avatar-placeholder {
  visibility: hidden;
}

.msg-bubble {
  padding: 0.72rem 0.96rem;
  font-size: 0.93rem;
  line-height: 1.5;
  border-radius: 12px;
  white-space: pre-wrap;
  transition: transform 180ms ease, box-shadow 220ms ease, background-color 220ms ease;
  box-shadow: 0 8px 24px rgba(8, 12, 20, 0.14);
}

.bot .msg-bubble {
  background: rgba(54, 60, 72, 0.78);
  border: 1px solid rgba(109, 121, 143, 0.32);
  color: #d7dae0;
}

.user .msg-bubble {
  background: linear-gradient(135deg, #4f78d1, #3964be);
  color: #f8fbff;
}

.msg-bubble p {
  margin: 0;
}

.plan-preview {
  min-width: min(92vw, 740px);
}

.plan-preview-head {
  margin-bottom: 0.5rem;
}

.plan-title {
  font-weight: 700;
}

.plan-meta {
  margin-top: 0.25rem !important;
  color: #c3cbda;
  font-size: 0.82rem;
}

.plan-table-wrap {
  overflow-x: auto;
  border: 1px solid rgba(109, 121, 143, 0.32);
  border-radius: 10px;
  background: rgba(22, 27, 35, 0.45);
}

.plan-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.plan-table th,
.plan-table td {
  border-bottom: 1px solid rgba(109, 121, 143, 0.22);
  text-align: left;
  padding: 0.42rem 0.5rem;
  vertical-align: top;
}

.plan-table th {
  font-weight: 600;
  color: #dce4f4;
  background: rgba(97, 175, 239, 0.1);
}

.plan-table tr:last-child td {
  border-bottom: none;
}

.plan-tail {
  margin-top: 0.45rem !important;
  font-size: 0.8rem;
  color: #b8c2d5;
}

.msg-wrapper:hover .msg-bubble {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(8, 12, 20, 0.2);
}

.bot .msg-bubble.msg-bubble--sticker {
  background: transparent;
  border: none;
  padding: 0;
}

.msg-bubble .msg-sticker {
  display: block;
  max-width: 152px;
  max-height: 152px;
  border-radius: 10px;
}

.bot .msg-bubble.error {
  border-color: rgba(233, 110, 110, 0.5);
  color: #ffc7c7;
}

.typing {
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8ba0cc;
  animation: typing 1.3s infinite ease-in-out both;
}

.typing span:nth-child(1) { animation-delay: -0.3s; }
.typing span:nth-child(2) { animation-delay: -0.15s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.input-container {
  padding: 0.92rem 1.2rem 1.1rem;
  border-top: 1px solid var(--od-border);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 0.55rem;
  border-radius: 12px;
  border: 1px solid rgba(106, 117, 136, 0.42);
  background: rgba(43, 49, 58, 0.8);
  padding: 0.5rem 0.58rem 0.5rem 0.8rem;
}

.input-wrapper:focus-within {
  border-color: rgba(97, 175, 239, 0.95);
  box-shadow: 0 0 0 2px rgba(97, 175, 239, 0.2);
}

.input-wrapper textarea {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  min-height: 2.2rem;
  max-height: 7rem;
  background: transparent;
  color: var(--od-text);
  font-size: 0.94rem;
  line-height: 1.5;
}

.input-wrapper textarea::placeholder {
  color: #8e98aa;
}

.send-btn {
  width: 34px;
  height: 34px;
  border: 1px solid rgba(126, 149, 201, 0.5);
  border-radius: 9px;
  background: rgba(70, 94, 153, 0.55);
  color: #dbe8ff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn.active {
  background: linear-gradient(135deg, #61afef, #4f95cf);
  border-color: rgba(181, 220, 250, 0.95);
}

.send-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.send-btn svg {
  width: 16px;
  height: 16px;
}

.soul-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.soul-label {
  font-size: 0.76rem;
  color: #8ca0c8;
}

.soul-btns {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.soul-btn {
  border: 1px solid rgba(132, 154, 203, 0.35);
  background: rgba(60, 82, 135, 0.22);
  color: #d4e0fb;
  border-radius: 999px;
  padding: 0.25rem 0.62rem;
  font-size: 0.73rem;
  cursor: pointer;
}

.soul-btn.active {
  border-color: rgba(162, 186, 238, 0.92);
  background: rgba(88, 114, 183, 0.48);
}

.msg-fade-enter-active,
.msg-fade-leave-active {
  transition: all 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.msg-fade-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.99);
}

@keyframes msg-appear {
  from { opacity: 0.2; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.sessions-scroll {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding-right: 0.2rem;
}

.session-title {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}

.session-title-wrap {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

.session-pin {
  font-size: 0.72rem;
}

.session-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.sidebar-item:hover .session-actions,
.sidebar-item.active .session-actions {
  opacity: 1;
}

.session-action {
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  width: 20px;
  height: 20px;
  border-radius: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  cursor: pointer;
}

.session-action:hover {
  border-color: rgba(126, 149, 201, 0.45);
  background: rgba(97, 175, 239, 0.2);
}

.session-action.danger:hover {
  border-color: rgba(240, 128, 128, 0.5);
  background: rgba(240, 128, 128, 0.2);
}

.session-time {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: var(--od-text-soft);
}

.sidebar-empty {
  color: var(--od-text-soft);
  font-size: 0.8rem;
  padding: 0.6rem 0.5rem;
}

@media (max-width: 980px) {
  .workspace-page {
    padding: 0;
  }

  .workspace-shell {
    width: 100%;
    height: 100vh;
    height: 100dvh;
    border-radius: 0;
  }

  .workspace-sidebar {
    display: none;
  }

  .sidebar-divider {
    display: none;
  }
}
</style>
