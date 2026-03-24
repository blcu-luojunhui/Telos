<template>
  <div class="login-wrapper">
    <div class="login-box">
      <h1 class="logo-text">注册 BetterMe</h1>
      <p class="subtitle">创建一个用户 ID 开始使用</p>

      <form @submit.prevent="register" class="login-form">
        <div class="input-group">
          <label for="userId">用户 ID</label>
          <input
            id="userId"
            v-model.trim="userId"
            type="text"
            placeholder="例如: user_001"
            required
            autocomplete="off"
          />
        </div>
        <div class="input-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="至少 6 位"
            required
            autocomplete="new-password"
          />
        </div>
        <div class="input-group">
          <label for="confirmPassword">确认密码</label>
          <input
            id="confirmPassword"
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入密码"
            required
            autocomplete="new-password"
          />
        </div>
        <button
          type="submit"
          class="login-btn"
          :disabled="!userId || !password || !confirmPassword || loading"
        >
          {{ loading ? '注册中...' : '注册并进入系统' }}
        </button>
      </form>
      <p v-if="errorText" class="error-text">{{ errorText }}</p>

      <p class="switch-link">
        已有账号？
        <router-link to="/">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { registerWithUserId, setAuthSession } from '../api/auth'

const router = useRouter()
const userId = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorText = ref('')

const register = async () => {
  if (!userId.value || !password.value || !confirmPassword.value || loading.value) return
  errorText.value = ''
  if (password.value !== confirmPassword.value) {
    errorText.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const data = await registerWithUserId(userId.value, password.value)
    setAuthSession({
      userId: data.user_id || userId.value,
      token: data.token || '',
    })
    router.push('/chat')
  } catch (e) {
    if (e && e.status === 409) {
      errorText.value = e.message || '该用户 ID 已存在（auth_users），请直接去登录'
    } else {
      errorText.value = e.message || '注册失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--bg-gradient);
}

.login-box {
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 24px;
  padding: 2.5rem 2rem;
  width: 100%;
  max-width: 400px;
  box-shadow: var(--input-shadow);
  text-align: center;
}

.logo-text {
  margin: 0 0 0.5rem;
  font-weight: 700;
  font-size: 1.6rem;
}

.subtitle {
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  text-align: left;
}

.input-group input {
  width: 100%;
  border: 1px solid var(--input-border);
  border-radius: 12px;
  padding: 0.8rem 0.9rem;
  background: var(--input-bg);
  color: var(--text-primary);
}

.login-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.switch-link {
  margin-top: 1rem;
  color: var(--text-secondary);
}

.error-text {
  margin-top: 0.8rem;
  color: #ef4444;
  font-size: 0.9rem;
}

.switch-link a {
  color: #10b981;
  text-decoration: none;
}
</style>
