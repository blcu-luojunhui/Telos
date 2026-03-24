<template>
  <div class="monitor-wrapper">
    <header class="monitor-header">
      <div class="header-left">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <span class="logo-text">BetterMe Monitor</span>
      </div>
      <div class="header-right">
        <div class="input-inline">
          <label>用户 ID</label>
          <input
            v-model.trim="filterUserId"
            type="text"
            placeholder="留空表示全部用户"
          />
        </div>
        <button type="button" class="btn" @click="loadConversations" :disabled="loadingList">
          刷新
        </button>
        <button type="button" class="btn-secondary" @click="backToChat">
          返回聊天
        </button>
      </div>
    </header>

    <main class="monitor-main">
      <section class="left-pane">
        <h2 class="section-title">会话列表</h2>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户</th>
                <th>状态</th>
                <th>消息数</th>
                <th>最近消息</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in conversations"
                :key="item.id"
                :class="{ active: item.id === selectedConvId }"
                @click="selectConversation(item.id)"
              >
                <td>{{ item.id }}</td>
                <td>{{ item.user_id }}</td>
                <td>{{ item.status }}</td>
                <td>{{ item.message_count }}</td>
                <td class="last-msg">
                  <span class="role-tag" :class="item.last_role">{{ item.last_role || '-' }}</span>
                  <span class="msg-preview">{{ item.last_message || '（无消息）' }}</span>
                </td>
                <td>{{ formatTime(item.updated_at) }}</td>
              </tr>
              <tr v-if="!loadingList && conversations.length === 0">
                <td colspan="6" class="empty">暂无数据</td>
              </tr>
              <tr v-if="loadingList">
                <td colspan="6" class="empty">加载中…</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="right-pane">
        <h2 class="section-title">
          会话详情
          <span v-if="detail?.conversation">#{{ detail.conversation.id }} / {{ detail.conversation.user_id }}</span>
        </h2>

        <div v-if="loadingDetail" class="detail-empty">正在加载会话详情…</div>
        <div v-else-if="!detail?.conversation" class="detail-empty">请选择左侧一条会话</div>
        <div v-else class="detail-body">
          <div class="detail-meta">
            <div><strong>状态：</strong>{{ detail.conversation.status }}</div>
            <div><strong>创建时间：</strong>{{ formatTime(detail.conversation.created_at) }}</div>
            <div><strong>更新时间：</strong>{{ formatTime(detail.conversation.updated_at) }}</div>
          </div>

          <div v-if="detail.pending" class="pending-box">
            <h3>当前 Pending</h3>
            <p class="pending-time">创建时间：{{ formatTime(detail.pending.created_at) }}</p>
            <div class="pending-json">
              <pre>{{ prettyJson(detail.pending) }}</pre>
            </div>
          </div>

          <div class="messages-box">
            <h3>消息流</h3>
            <div v-if="detail.messages.length === 0" class="detail-empty-small">暂无消息</div>
            <ul v-else class="msg-list">
              <li
                v-for="m in detail.messages"
                :key="m.id"
                :class="['msg-item', m.role, { error: m.msg_type === 'error' }]"
              >
                <div class="msg-header">
                  <span class="role-tag" :class="m.role">{{ m.role }}</span>
                  <span class="msg-type" v-if="m.msg_type">{{ m.msg_type }}</span>
                  <span class="msg-time">{{ formatTime(m.created_at) }}</span>
                </div>
                <div class="msg-content">{{ m.content }}</div>
                <pre v-if="m.extra" class="msg-extra">{{ prettyJson(m.extra) }}</pre>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listConversations, getConversationDetail } from '../api/monitor'

const router = useRouter()

const filterUserId = ref('')
const conversations = ref([])
const selectedConvId = ref(null)
const detail = ref(null)
const loadingList = ref(false)
const loadingDetail = ref(false)

function formatTime(val) {
  if (!val) return ''
  try {
    const d = new Date(val)
    if (Number.isNaN(d.getTime())) return String(val)
    return d.toLocaleString()
  } catch {
    return String(val)
  }
}

function prettyJson(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function loadConversations() {
  loadingList.value = true
  try {
    const res = await listConversations({
      user_id: filterUserId.value || undefined,
      limit: 50,
    })
    conversations.value = Array.isArray(res.items) ? res.items : []
    if (conversations.value.length > 0) {
      // 如果当前选中的会话不在列表中，自动选中第一个
      if (!selectedConvId.value || !conversations.value.some(c => c.id === selectedConvId.value)) {
        selectedConvId.value = conversations.value[0].id
        await loadDetail(selectedConvId.value)
      }
    } else {
      selectedConvId.value = null
      detail.value = null
    }
  } catch (e) {
    console.error(e)
  } finally {
    loadingList.value = false
  }
}

async function loadDetail(convId) {
  if (!convId) {
    detail.value = null
    return
  }
  loadingDetail.value = true
  try {
    detail.value = await getConversationDetail(convId)
  } catch (e) {
    console.error(e)
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function selectConversation(id) {
  if (id === selectedConvId.value) return
  selectedConvId.value = id
  loadDetail(id)
}

function backToChat() {
  router.push('/chat')
}

onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
.monitor-wrapper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
}

.monitor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  background: var(--header-bg);
  border-bottom: 1px solid var(--header-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.logo-icon {
  width: 28px;
  height: 28px;
  color: #10b981;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
}

.logo-text {
  font-weight: 600;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.input-inline {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.input-inline label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.input-inline input {
  min-width: 160px;
  padding: 0.35rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--input-border);
  background: var(--input-bg);
  color: var(--text-primary);
  outline: none;
}

.btn,
.btn-secondary {
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn {
  background: #10b981;
  color: white;
  border-color: #10b981;
}

.btn:hover {
  background: #059669;
  border-color: #059669;
}

.btn-secondary {
  background: var(--id-wrap-bg);
  color: var(--text-primary);
  border-color: var(--id-wrap-border);
}

.btn-secondary:hover {
  background: var(--input-bg);
}

.monitor-main {
  flex: 1;
  display: flex;
  min-height: 0;
}

.left-pane {
  width: 45%;
  border-right: 1px solid var(--header-border);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.right-pane {
  flex: 1;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.section-title {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.section-title span {
  font-weight: 400;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid var(--header-border);
  background: rgba(255, 255, 255, 0.6);
}

[data-theme="dark"] .table-wrapper {
  background: rgba(17, 24, 39, 0.5);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

thead {
  background: rgba(249, 250, 251, 0.9);
}

[data-theme="dark"] thead {
  background: rgba(31, 41, 55, 0.9);
}

th,
td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--header-border);
  text-align: left;
}

tbody tr:hover {
  background: rgba(16, 185, 129, 0.06);
}

tbody tr.active {
  background: rgba(16, 185, 129, 0.12);
}

.last-msg {
  max-width: 260px;
}

.role-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  font-size: 0.75rem;
  margin-right: 0.25rem;
  background: var(--id-wrap-bg);
  color: var(--text-secondary);
}

.role-tag.user {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.role-tag.assistant {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.msg-preview {
  display: inline-block;
  max-width: 190px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty {
  text-align: center;
  color: var(--text-secondary);
}

.detail-empty {
  padding: 1rem;
  color: var(--text-secondary);
}

.detail-empty-small {
  padding: 0.75rem;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  height: 100%;
  min-height: 0;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.85rem;
}

.pending-box {
  border-radius: 10px;
  border: 1px solid rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.05);
  padding: 0.75rem;
}

.pending-box h3 {
  margin: 0 0 0.35rem;
  font-size: 0.9rem;
}

.pending-time {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.pending-json pre {
  margin: 0;
  font-size: 0.75rem;
  white-space: pre-wrap;
  word-break: break-all;
}

.messages-box {
  flex: 1;
  min-height: 0;
  border-radius: 10px;
  border: 1px solid var(--header-border);
  background: rgba(255, 255, 255, 0.6);
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
}

[data-theme="dark"] .messages-box {
  background: rgba(17, 24, 39, 0.5);
}

.messages-box h3 {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
}

.msg-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow: auto;
  flex: 1;
}

.msg-item {
  padding: 0.45rem 0.5rem;
  border-bottom: 1px dashed var(--header-border);
  font-size: 0.82rem;
}

.msg-item:last-child {
  border-bottom: none;
}

.msg-item.error {
  background: rgba(248, 113, 113, 0.08);
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.2rem;
}

.msg-type {
  font-size: 0.7rem;
  padding: 0.05rem 0.35rem;
  border-radius: 999px;
  background: var(--id-wrap-bg);
  color: var(--text-secondary);
}

.msg-time {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-extra {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  background: rgba(15, 23, 42, 0.04);
  padding: 0.35rem;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}

@media (max-width: 900px) {
  .monitor-main {
    flex-direction: column;
  }
  .left-pane {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--header-border);
  }
}
</style>

