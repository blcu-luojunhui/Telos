<template>
  <div class="oauth-callback">
    <div class="card">
      <h2>Processing Third-Party Login</h2>
      <p>{{ message }}</p>
      <button v-if="failed" type="button" @click="goLogin">Back to Login</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { exchangeOAuthCode, setAuthSession } from '../api/auth'

const router = useRouter()
const message = ref('Verifying authorization data...')
const failed = ref(false)

const goLogin = () => router.replace('/')

onMounted(async () => {
  const url = new URL(window.location.href)
  const code = (url.searchParams.get('code') || '').trim()
  const state = (url.searchParams.get('state') || '').trim()
  const provider = (url.searchParams.get('provider') || '').trim().toLowerCase() || 'google'

  if (!code) {
    message.value = 'Missing authorization code. Unable to continue login.'
    failed.value = true
    return
  }

  const stateKey = `betterme_oauth_state_${provider}`
  const expectedState = localStorage.getItem(stateKey) || ''
  if (expectedState && state && expectedState !== state) {
    message.value = 'Authorization state check failed. Please start login again.'
    failed.value = true
    return
  }

  try {
    const redirectUri = `${window.location.origin}/oauth/callback?provider=${provider}`
    const data = await exchangeOAuthCode(provider, code, redirectUri)
    setAuthSession({
      userId: data.user_id || '',
      token: data.token || '',
    })
    localStorage.removeItem(stateKey)
    message.value = 'Login successful. Redirecting...'
    router.replace('/chat')
  } catch (e) {
    message.value = e.message || 'OAuth login failed. Please try again later.'
    failed.value = true
  }
})
</script>

<style scoped>
.oauth-callback {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at top, #1b2435, #070d18);
  padding: 20px;
}

.card {
  width: min(440px, 100%);
  border: 1px solid rgba(173, 205, 248, 0.2);
  border-radius: 18px;
  background: rgba(11, 19, 31, 0.9);
  padding: 24px;
  text-align: center;
}

h2 {
  margin: 0 0 8px;
  color: #e9f2ff;
}

p {
  margin: 0 0 16px;
  color: #9fb4d5;
}

button {
  border: 1px solid rgba(153, 188, 235, 0.22);
  border-radius: 10px;
  padding: 9px 14px;
  background: rgba(29, 48, 74, 0.8);
  color: #e8f3ff;
  cursor: pointer;
}
</style>
