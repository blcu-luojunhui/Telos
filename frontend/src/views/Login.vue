<template>
  <div class="login-wrapper">
    <div class="login-box">
      <div class="logo-icon">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <h1 class="logo-text">BetterMe</h1>
      <p class="subtitle">登入你的私人教练与生活顾问</p>

      <form @submit.prevent="login" class="login-form">
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
            placeholder="请输入密码"
            required
            autocomplete="current-password"
          />
        </div>
        <button type="submit" class="login-btn" :disabled="!userId || !password || loading">
          {{ loading ? '登录中...' : '进入系统' }}
        </button>
      </form>
      <p class="register-link">
        还没有账号？
        <router-link to="/register">去注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { loginWithUserId, setAuthSession } from '../api/auth'

const router = useRouter()
const userId = ref('')
const password = ref('')
const loading = ref(false)

onMounted(() => {
  document.documentElement.setAttribute('data-theme', 'dark')
  localStorage.setItem('betterme_theme', 'dark')
})

const login = async () => {
  if (!userId.value || !password.value || loading.value) return
  loading.value = true
  try {
    const data = await loginWithUserId(userId.value, password.value)
    setAuthSession({
      userId: data.user_id || userId.value,
      token: data.token || '',
    })
    router.push('/chat')
  } catch (e) {
    alert(e.message || '登录失败，请稍后重试')
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
  position: relative;
  transition: background 0.3s ease;
}

.login-box {
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 24px;
  padding: 3rem 2.5rem;
  width: 100%;
  max-width: 400px;
  box-shadow: var(--input-shadow);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  text-align: center;
  animation: fadeIn 0.5s ease-out;
  margin: 0 1rem;
}

.logo-icon {
  width: 56px;
  height: 56px;
  color: #10b981;
  margin: 0 auto 1rem;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
}

.logo-text {
  margin: 0 0 0.5rem;
  font-weight: 700;
  font-size: 1.75rem;
  letter-spacing: -0.02em;
  background: linear-gradient(to right, #34d399, #10b981);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.95rem;
  margin-bottom: 2rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  text-align: left;
}

.input-group label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  margin-left: 0.25rem;
}

.input-group input {
  width: 100%;
  background: var(--bg-color-solid, transparent);
  border: 1px solid var(--input-border);
  color: var(--text-primary);
  font-size: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  outline: none;
  transition: all 0.2s ease;
  background-color: rgba(0,0,0,0.02);
}

[data-theme="dark"] .input-group input {
  background-color: rgba(0,0,0,0.2);
}

.input-group input:focus {
  border-color: rgba(16, 185, 129, 0.5);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
}

.login-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 0.9rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
}

.login-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.register-link {
  margin-top: 1rem;
  color: var(--text-secondary);
}

.register-link a {
  color: #10b981;
  text-decoration: none;
}
</style>
